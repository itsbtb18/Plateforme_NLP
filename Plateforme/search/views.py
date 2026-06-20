import re
import logging
from typing import Optional, Dict, Any, List, Tuple

from django.views.generic import TemplateView
from django.http import JsonResponse
from django.views import View
from django.urls import reverse
from django.utils.html import mark_safe, escape as html_escape
from django.contrib.auth import get_user_model
from django.db.models import Q as DJQ

from elasticsearch_dsl import Q, Search
from elasticsearch.exceptions import ConnectionError, NotFoundError
from accounts.blocking import blocked_user_ids_for

from .documents import (
    CourseDocument, ToolDocument, CorpusDocument,
    ResourceDocument, ProjectDocument, EventDocument,
    InstitutionDocument, UserDocument
)

logger = logging.getLogger(__name__)
User = get_user_model()


def detect_language(query: str) -> str:
    """Detect if query is primarily Arabic or English."""
    if not query:
        return 'english'
    
    arabic_pattern = re.compile(r'[\u0600-\u06FF\u0750-\u077F\u08A0-\u08FF]+')
    arabic_chars = len(arabic_pattern.findall(query))
    total_chars = len(query.replace(' ', ''))
    
    if total_chars == 0:
        return 'english'
    
    if arabic_chars / total_chars > 0.3:
        return 'arabic'
    return 'english'


class GlobalSearchView(TemplateView):
    template_name = 'search/search_results.html'
    
    # FIXED: date_field mapping to match your Document classes exactly
    # Document configurations matching the updated documents.py
    # All title/description fields now have phonetic analyzer for dis_max ranking
    DOCUMENT_CONFIGS = {
        'course': {
            'document': CourseDocument,
            'url_name': 'resources:course_detail',
            'url_field': 'pk',
            'fields': {
                'title': ['title', 'title.arabic', 'title.english', 'title.phonetic'],
                'description': ['description', 'description.arabic', 'description.english', 'description.phonetic'],
                'keywords': ['keywords', 'keywords.arabic', 'keywords.english', 'keywords.phonetic'],
            },
            'extra_fields': ['language', 'academic_level', 'field', 'author'],
            'date_field': 'creation_date',
        },
        'tool': {
            'document': ToolDocument,
            'url_name': 'resources:tool_detail',
            'url_field': 'pk',
            'fields': {
                'title': ['title', 'title.arabic', 'title.english', 'title.phonetic'],
                'description': ['description', 'description.arabic', 'description.english', 'description.phonetic'],
                'keywords': ['keywords', 'keywords.arabic', 'keywords.english', 'keywords.phonetic'],
            },
            'extra_fields': ['language', 'tool_type', 'author'],
            'date_field': 'creation_date',
        },
        'corpus': {
            'document': CorpusDocument,
            'url_name': 'resources:corpus_detail',
            'url_field': 'pk',
            'fields': {
                'title': ['title', 'title.arabic', 'title.english', 'title.phonetic'],
                'description': ['description', 'description.arabic', 'description.english', 'description.phonetic'],
                'keywords': ['keywords', 'keywords.arabic', 'keywords.english', 'keywords.phonetic'],
            },
            'extra_fields': ['language', 'field', 'author'],
            'date_field': 'creation_date',
        },
        'resource': {
            'document': ResourceDocument,
            'url_name': 'resources:resource-detail',
            'url_field': 'pk',
            'url_extra_kwargs': lambda hit: {'type': getattr(hit, 'document_type', 'article')},
            'fields': {
                'title': ['title', 'title.arabic', 'title.english', 'title.phonetic'],
                'description': ['description', 'description.arabic', 'description.english', 'description.phonetic'],
                'keywords': ['keywords', 'keywords.arabic', 'keywords.english', 'keywords.phonetic'],
            },
            'extra_fields': ['document_type', 'author'],
            'date_field': 'creation_date',
        },
        'project': {
            'document': ProjectDocument,
            'url_name': 'projects:project_detail',
            'url_field': 'pk',
            'fields': {
                'title': ['title', 'title.arabic', 'title.english', 'title.phonetic'],
                'description': ['description', 'description.arabic', 'description.english', 'description.phonetic'],
            },
            'extra_fields': ['status', 'coordinator', 'institution'],
            'date_field': 'created_at',  # Project uses created_at for sorting
        },
        'event': {
            'document': EventDocument,
            'url_name': 'events:event_detail',
            'url_field': 'pk',
            'fields': {
                'title': ['title', 'title.arabic', 'title.english', 'title.phonetic'],
                'description': ['description', 'description.arabic', 'description.english', 'description.phonetic'],
            },
            'extra_fields': ['event_type', 'location', 'organizer'],
            'date_field': 'start_date',  # Event uses start_date for sorting
        },
        'institution': {
            'document': InstitutionDocument,
            'url_name': 'institutions:institution_detail',
            'url_field': 'pk',
            'fields': {
                'name': ['name', 'name.arabic', 'name.english', 'name.phonetic'],
                'acronym': ['acronym', 'acronym.arabic', 'acronym.english'],
                'description': ['description', 'description.arabic', 'description.english', 'description.phonetic'],
            },
            'extra_fields': ['institution_type', 'country', 'city'],
            'date_field': None,
        },
        'user': {
            'document': UserDocument,
            'url_name': 'accounts:profile',
            'url_field': 'pk',
            'fields': {
                'full_name': ['full_name', 'full_name.arabic', 'full_name.english', 'full_name.phonetic'],
                'email': ['email'],
            },
            'extra_fields': ['bio'],
            'date_field': None,
        },
    }

    def _build_dis_max_query(self, query: str, doc_type: str, detected_lang: str) -> Q:
        config = self.DOCUMENT_CONFIGS[doc_type]
        queries = []
        
        primary_suffix = f'.{detected_lang}' if detected_lang in ('arabic', 'english') else ''
        secondary_suffix = '.english' if detected_lang == 'arabic' else '.arabic'
        
        for field_group, field_list in config['fields'].items():
            for field in field_list:
                if primary_suffix and field.endswith(primary_suffix):
                    boost = 3.0
                elif field.endswith('.phonetic'):
                    boost = 0.5
                elif secondary_suffix and field.endswith(secondary_suffix):
                    boost = 1.0
                elif '.' not in field or field.endswith('.raw'):
                    boost = 2.0
                else:
                    boost = 1.5
                
                if field_group == 'title' or field_group == 'name':
                    boost *= 1.5
                
                queries.append(Q('match', **{field: {'query': query, 'boost': boost}}))
        
        return Q('dis_max', queries=queries, tie_breaker=0.3)

    def _build_search(self, query: str, doc_type: str, detected_lang: str, filters: Dict[str, Any], highlight: bool = True) -> Search:
        config = self.DOCUMENT_CONFIGS[doc_type]
        doc_class = config['document']
        search = doc_class.search()
        
        dis_max_q = self._build_dis_max_query(query, doc_type, detected_lang)
        search = search.query(dis_max_q)
        
        # Filtering logic
        if filters.get('language') and 'language' in [f.split('.')[0] for f in sum(config['fields'].values(), []) + config.get('extra_fields', [])]:
            search = search.filter('term', **{'language.raw': filters['language']})
        
        if filters.get('academic_level') and doc_type == 'course':
            search = search.filter('term', **{'academic_level.raw': filters['academic_level']})
        
        date_field = config.get('date_field')
        if date_field and filters.get('date_from'):
            search = search.filter('range', **{date_field: {'gte': filters['date_from']}})
        if date_field and filters.get('date_to'):
            search = search.filter('range', **{date_field: {'lte': filters['date_to']}})
        
        if highlight:
            search = search.highlight_options(order='score', encoder='html')
            for field_list in config['fields'].values():
                for field in field_list:
                    if not field.endswith('.raw'):
                        search = search.highlight(field, pre_tags=['<mark>'], post_tags=['</mark>'], fragment_size=200)
        
        return search

    def _execute_multi_search(
        self,
        query: str,
        detected_lang: str,
        filters: Dict[str, Any],
        type_filter: Optional[str] = None,
        page: int = 1,
        per_page: int = 20,
        hidden_user_ids: Optional[set[str]] = None,
    ) -> Tuple[List[Dict], Dict[str, int], int]:
        results = []
        aggregations = {}
        total_count = 0
        hidden_user_ids = hidden_user_ids or set()
        
        doc_types = [type_filter] if type_filter and type_filter in self.DOCUMENT_CONFIGS else self.DOCUMENT_CONFIGS.keys()
        
        for doc_type in self.DOCUMENT_CONFIGS.keys():
            try:
                search = self._build_search(query, doc_type, detected_lang, filters, highlight=False)
                response = search[:0].execute()
                aggregations[doc_type] = response.hits.total.value
            except Exception:
                aggregations[doc_type] = 0
        
        offset = (page - 1) * per_page
        for doc_type in doc_types:
            try:
                search = self._build_search(query, doc_type, detected_lang, filters, highlight=True)
                if type_filter:
                    search = search[offset:offset + per_page]
                else:
                    search = search[:5] # Limit per type in mixed view
                
                sort_by = filters.get('sort_by', 'relevance')
                date_f = self.DOCUMENT_CONFIGS[doc_type].get('date_field')
                if sort_by == 'newest' and date_f:
                    search = search.sort({date_f: {'order': 'desc', 'unmapped_type': 'date'}})
                elif sort_by == 'oldest' and date_f:
                    search = search.sort({date_f: {'order': 'asc', 'unmapped_type': 'date'}})
                
                response = search.execute()
                for hit in response:
                    if doc_type == "user" and str(hit.meta.id) in hidden_user_ids:
                        continue
                    res = self._format_result(hit, doc_type, self.DOCUMENT_CONFIGS[doc_type])
                    if res: results.append(res)
                
                if type_filter:
                    total_count = response.hits.total.value
            except Exception as e:
                logger.error(f"Search error for {doc_type}: {e}")
        
        if not type_filter:
            total_count = sum(aggregations.values())
            results.sort(key=lambda x: x.get('score') or 0, reverse=True)
            results = results[:per_page]
        
        return results, aggregations, total_count

    @staticmethod
    def _sanitize_highlight(fragment: str) -> str:
        """
        Sanitize Elasticsearch highlight fragments to prevent XSS.
        Preserves only <mark> and </mark> tags, escapes everything else.
        """
        # Temporarily replace ES highlight tags
        safe = fragment.replace('<mark>', '\x00MARK_OPEN\x00').replace('</mark>', '\x00MARK_CLOSE\x00')
        # Escape all HTML in the remaining content
        safe = html_escape(safe)
        # Restore the highlight tags
        safe = safe.replace('\x00MARK_OPEN\x00', '<mark>').replace('\x00MARK_CLOSE\x00', '</mark>')
        return safe

    def _format_result(self, hit, doc_type: str, config: Dict) -> Optional[Dict]:
        try:
            highlight = {}
            if hasattr(hit.meta, 'highlight'):
                for field, fragments in hit.meta.highlight.to_dict().items():
                    base_field = field.split('.')[0]
                    if base_field not in highlight:
                        highlight[base_field] = mark_safe(self._sanitize_highlight(fragments[0]))
            
            title = ''
            if doc_type == 'institution': title = highlight.get('name') or getattr(hit, 'name', '')
            elif doc_type == 'user': title = highlight.get('full_name') or getattr(hit, 'full_name', '')
            else: title = highlight.get('title') or getattr(hit, 'title', '')
            
            try:
                url_kwargs = {config['url_field']: hit.meta.id}
                extra = config.get('url_extra_kwargs', {})
                if callable(extra):
                    extra = extra(hit)
                url_kwargs.update(extra)
                url = reverse(config['url_name'], kwargs=url_kwargs)
            except: url = '#'
            
            result = {
                'type': doc_type,
                'title': title,
                'description': highlight.get('description') or getattr(hit, 'description', ''),
                'link': url,
                'score': hit.meta.score,
            }
            
            # Add dynamic fields based on doc_type
            if doc_type == 'user':
                # Add avatar and bio for user results
                result['avatar'] = getattr(hit, 'avatar', '')
                result['bio'] = getattr(hit, 'bio', '')
                result['email'] = getattr(hit, 'email', '')
            elif doc_type == 'course':
                result['language'] = getattr(hit, 'language', '')
                result['academic_level'] = getattr(hit, 'academic_level', '')
                result['field'] = getattr(hit, 'field', '')
                if hasattr(hit, 'author') and isinstance(hit.author, dict):
                    result['author'] = hit.author.get('full_name', '')
            elif doc_type == 'tool':
                result['language'] = getattr(hit, 'language', '')
                result['tool_type'] = getattr(hit, 'tool_type', '')
                if hasattr(hit, 'author') and isinstance(hit.author, dict):
                    result['author'] = hit.author.get('full_name', '')
            elif doc_type == 'corpus':
                result['language'] = getattr(hit, 'language', '')
                result['field'] = getattr(hit, 'field', '')
                if hasattr(hit, 'author') and isinstance(hit.author, dict):
                    result['author'] = hit.author.get('full_name', '')
            elif doc_type == 'resource':
                result['document_type'] = getattr(hit, 'document_type', '')
                if hasattr(hit, 'author') and isinstance(hit.author, dict):
                    result['author'] = hit.author.get('full_name', '')
            elif doc_type == 'project':
                result['status'] = getattr(hit, 'status', '')
                result['coordinator'] = getattr(hit, 'coordinator', '')
                result['institution'] = getattr(hit, 'institution', '')
            elif doc_type == 'event':
                result['event_type'] = getattr(hit, 'event_type', '')
                result['location'] = getattr(hit, 'location', '')
                result['organizer'] = getattr(hit, 'organizer', '')
            elif doc_type == 'institution':
                result['institution_type'] = getattr(hit, 'institution_type', '')
                result['country'] = getattr(hit, 'country', '')
                result['city'] = getattr(hit, 'city', '')
                result['acronym'] = getattr(hit, 'acronym', '')
            
            return result
        except Exception: return None

    def get(self, request, *args, **kwargs):
        """Handle both AJAX and regular requests."""
        # Check if this is an AJAX request
        is_ajax = request.headers.get('X-Requested-With') == 'XMLHttpRequest'
        
        if is_ajax:
            return self._handle_ajax_request(request)
        
        # Regular HTML request
        return super().get(request, *args, **kwargs)
    
    def _handle_ajax_request(self, request):
        """Return JSON response for AJAX autocomplete requests."""
        q = request.GET.get('q', '').strip()
        
        if not q or len(q) < 1:
            return JsonResponse({'results': [], 'total': 0})
        
        detected_lang = detect_language(q)
        filters = {}
        hidden_user_ids = {str(pk) for pk in blocked_user_ids_for(request.user)}
        
        try:
            results, aggs, total = self._execute_multi_search(
                q, detected_lang, filters, 
                type_filter=None, page=1, per_page=8,
                hidden_user_ids=hidden_user_ids,
            )
            
            # Clean results for JSON (remove mark_safe objects)
            json_results = []
            for r in results:
                result_item = {
                    'title': str(r.get('title', '')).replace('<mark>', '').replace('</mark>', ''),
                    'type': r.get('type', ''),
                    'link': r.get('link', '#'),
                    'field': r.get('field', r.get('language', '')),
                    'language': r.get('language', ''),
                }
                # Add avatar for user results
                if r.get('type') == 'user' and r.get('avatar'):
                    result_item['avatar'] = r.get('avatar', '')
                json_results.append(result_item)
            
            return JsonResponse({
                'results': json_results,
                'total': total,
                'query': q,
            })
        except (ConnectionError, NotFoundError) as e:
            logger.error(f"Elasticsearch connection error: {e}")
            return JsonResponse({'results': [], 'total': 0, 'error': 'Search service unavailable'})
        except Exception as e:
            logger.error(f"Search error: {e}")
            return JsonResponse({'results': [], 'total': 0, 'error': 'Search failed'})

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        q = self.request.GET.get('q', '').strip()
        t = self.request.GET.get('type', '').strip() or None
        
        filters = {
            'language': self.request.GET.get('language'),
            'academic_level': self.request.GET.get('academic_level'),
            'date_from': self.request.GET.get('date_from'),
            'date_to': self.request.GET.get('date_to'),
            'sort_by': self.request.GET.get('sort_by', 'relevance'),
        }
        
        page = int(self.request.GET.get('page', 1))
        per_page = 20
        
        if q:
            lang = detect_language(q)
            hidden_user_ids = {str(pk) for pk in blocked_user_ids_for(self.request.user)}
            try:
                results, aggs, total = self._execute_multi_search(
                    q,
                    lang,
                    filters,
                    t,
                    page,
                    per_page,
                    hidden_user_ids=hidden_user_ids,
                )
                context.update({
                    'results': results, 'aggregations': aggs, 'total': total,
                    'query': q, 'detected_language': lang, 'current_page': page
                })
                # Pagination math
                total_pages = (total + per_page - 1) // per_page
                context['page_range'] = range(1, total_pages + 1)
            except (ConnectionError, NotFoundError):
                context['fallback_mode'] = True

        context['filters'] = filters
        context.setdefault('query', q)
        return context

class SearchAutocompleteView(View):
    """
    Fast autocomplete endpoint for search suggestions.
    Uses multi_match with fuzziness for typo-tolerant suggestions.
    """
    
    AUTOCOMPLETE_DOCS = {
        'course': {
            'document': CourseDocument,
            'url_name': 'resources:course_detail',
            'title_field': 'title',
            'fields': ['title', 'title.arabic', 'title.english', 'keywords'],
        },
        'tool': {
            'document': ToolDocument,
            'url_name': 'resources:tool_detail',
            'title_field': 'title',
            'fields': ['title', 'title.arabic', 'title.english', 'keywords'],
        },
        'corpus': {
            'document': CorpusDocument,
            'url_name': 'resources:corpus_detail',
            'title_field': 'title',
            'fields': ['title', 'title.arabic', 'title.english', 'keywords'],
        },
        'project': {
            'document': ProjectDocument,
            'url_name': 'projects:project_detail',
            'title_field': 'title',
            'fields': ['title', 'title.arabic', 'title.english'],
        },
        'user': {
            'document': UserDocument,
            'url_name': 'accounts:profile',
            'title_field': 'full_name',
            'fields': ['full_name', 'full_name.arabic', 'full_name.english', 'full_name.phonetic', 'email'],
        },
    }

    @staticmethod
    def _visible_user_ids(user_ids, hidden_user_ids: set[str]) -> set[str]:
        if not user_ids:
            return set()
        return {
            str(pk)
            for pk in User.objects.filter(id__in=user_ids, is_active=True)
            .exclude(status="blocked")
            .exclude(id__in=hidden_user_ids)
            .values_list("id", flat=True)
        }
    
    def get(self, request, *args, **kwargs):
        q = request.GET.get('q', '').strip()
        
        if len(q) < 2:
            return JsonResponse({'suggestions': []})
        
        detected_lang = detect_language(q)
        suggestions = []
        seen_keys = set()
        hidden_user_ids = {str(pk) for pk in blocked_user_ids_for(request.user)}
        
        for doc_type, config in self.AUTOCOMPLETE_DOCS.items():
            try:
                doc_class = config['document']
                search = doc_class.search()
                
                # Build multi_match query with fuzziness
                multi_match_query = Q(
                    'multi_match',
                    query=q,
                    fields=config['fields'],
                    type='best_fields',
                    fuzziness='AUTO',
                    prefix_length=1,
                    minimum_should_match='75%',
                )
                
                # Boost by language match
                if doc_type == 'user':
                    boost_query = Q(
                        'bool',
                        should=[
                            Q('match', **{'full_name.arabic': {'query': q, 'boost': 2.5}}),
                            Q('match', **{'full_name.english': {'query': q, 'boost': 2.5}}),
                            Q('match', **{'full_name': {'query': q, 'boost': 2.0}}),
                            Q('match', **{'email': {'query': q, 'boost': 2.2}}),
                        ],
                        minimum_should_match=1,
                    )
                elif detected_lang == 'arabic':
                    boost_query = Q('match', **{'title.arabic': {'query': q, 'boost': 2.0}})
                else:
                    boost_query = Q('match', **{'title.english': {'query': q, 'boost': 2.0}})
                
                # Combine queries
                search = search.query(
                    Q('bool', should=[multi_match_query, boost_query], minimum_should_match=1)
                )
                
                # Only get top 3 per type for quick suggestions
                search = search[:5] if doc_type == 'user' else search[:3]
                
                # For user type, also fetch avatar
                if doc_type == 'user':
                    search = search.source([config['title_field'], 'avatar', 'email'])
                else:
                    search = search.source([config['title_field']])
                
                response = search.execute()
                visible_user_ids = set()
                if doc_type == "user":
                    visible_user_ids = self._visible_user_ids(
                        [str(hit.meta.id) for hit in response],
                        hidden_user_ids,
                    )
                
                for hit in response:
                    if doc_type == "user" and str(hit.meta.id) not in visible_user_ids:
                        continue
                    title = getattr(hit, config['title_field'], '')
                    if title:
                        try:
                            url = reverse(config['url_name'], kwargs={'pk': hit.meta.id})
                        except:
                            url = '#'
                        
                        suggestion = {
                            'title': str(title),
                            'type': doc_type,
                            'link': url,
                            'score': hit.meta.score,
                        }
                        
                        # Add avatar for user type
                        if doc_type == 'user':
                            avatar = getattr(hit, 'avatar', '')
                            if avatar:
                                suggestion['avatar'] = avatar
                            email = getattr(hit, 'email', '')
                            if email and str(email) != str(title):
                                suggestion['subtitle'] = str(email)
                            seen_keys.add(("user", str(hit.meta.id)))
                        else:
                            seen_keys.add((doc_type, str(hit.meta.id)))
                        
                        suggestions.append(suggestion)
            except Exception as e:
                logger.warning(f"Autocomplete error for {doc_type}: {e}")
                continue

        # DB fallback for users by name/email (works even when ES index is stale)
        # This guarantees profile lookup by full name, not only email.
        try:
            user_qs = (
                User.objects.filter(
                    DJQ(full_name_en__icontains=q)
                    | DJQ(full_name_ar__icontains=q)
                    | DJQ(full_name__icontains=q)
                    | DJQ(email__icontains=q)
                )
                .filter(is_active=True)
                .exclude(status="blocked")
                .exclude(id__in=hidden_user_ids)
                .only("id", "email", "full_name_en", "full_name_ar", "full_name", "avatar")
                [:8]
            )
            for u in user_qs:
                key = ("user", str(u.id))
                if key in seen_keys:
                    continue
                title = (u.get_full_name_display or "").strip() or u.email
                if not title:
                    continue
                suggestion = {
                    "title": title,
                    "type": "user",
                    "link": reverse("accounts:profile", kwargs={"pk": u.id}),
                    "score": 10.0,
                }
                if u.email and u.email != title:
                    suggestion["subtitle"] = u.email
                if getattr(u, "avatar", None):
                    try:
                        suggestion["avatar"] = u.avatar.url
                    except Exception:
                        pass
                suggestions.append(suggestion)
                seen_keys.add(key)
        except Exception as e:
            logger.warning(f"Autocomplete DB user fallback error: {e}")
        
        # Sort by score and limit to top 8
        suggestions.sort(
            key=lambda x: (
                0 if x.get('type') == 'user' else 1,
                -(x.get('score', 0) or 0),
                x.get('title', '').lower(),
            )
        )
        suggestions = suggestions[:8]
        
        # Remove score from response
        for s in suggestions:
            s.pop('score', None)
        
        return JsonResponse({'suggestions': suggestions})
    
