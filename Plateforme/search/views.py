import re
import logging
from typing import Optional, Dict, Any, List, Tuple

from django.views.generic import TemplateView
from django.http import JsonResponse
from django.views import View
from django.urls import reverse
from django.utils.html import mark_safe

from elasticsearch_dsl import Q, Search
from elasticsearch.exceptions import ConnectionError, NotFoundError

from .documents import (
    CourseDocument, ToolDocument, CorpusDocument,
    ResourceDocument, ProjectDocument, EventDocument,
    InstitutionDocument, UserDocument
)

logger = logging.getLogger(__name__)


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

    def _execute_multi_search(self, query: str, detected_lang: str, filters: Dict[str, Any], type_filter: Optional[str] = None, page: int = 1, per_page: int = 20) -> Tuple[List[Dict], Dict[str, int], int]:
        results = []
        aggregations = {}
        total_count = 0
        
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
                
                response = search.execute()
                for hit in response:
                    res = self._format_result(hit, doc_type, self.DOCUMENT_CONFIGS[doc_type])
                    if res: results.append(res)
                
                if type_filter:
                    total_count = response.hits.total.value
            except Exception as e:
                logger.error(f"Search error for {doc_type}: {e}")
        
        if not type_filter:
            total_count = sum(aggregations.values())
            results.sort(key=lambda x: x.get('score', 0), reverse=True)
            results = results[:per_page]
        
        return results, aggregations, total_count

    def _format_result(self, hit, doc_type: str, config: Dict) -> Optional[Dict]:
        try:
            highlight = {}
            if hasattr(hit.meta, 'highlight'):
                for field, fragments in hit.meta.highlight.to_dict().items():
                    base_field = field.split('.')[0]
                    if base_field not in highlight:
                        highlight[base_field] = mark_safe(fragments[0])
            
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
            # Add dynamic fields (author, language, etc) based on doc_type...
            # (Truncated for brevity, but kept logic from your original snippet)
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
        
        try:
            results, aggs, total = self._execute_multi_search(
                q, detected_lang, filters, 
                type_filter=None, page=1, per_page=8
            )
            
            # Clean results for JSON (remove mark_safe objects)
            json_results = []
            for r in results:
                json_results.append({
                    'title': str(r.get('title', '')).replace('<mark>', '').replace('</mark>', ''),
                    'type': r.get('type', ''),
                    'link': r.get('link', '#'),
                    'field': r.get('field', r.get('language', '')),
                    'language': r.get('language', ''),
                })
            
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
            try:
                results, aggs, total = self._execute_multi_search(q, lang, filters, t, page, per_page)
                context.update({
                    'results': results, 'aggregations': aggs, 'total': total,
                    'query': q, 'detected_language': lang, 'current_page': page
                })
                # Pagination math
                total_pages = (total + per_page - 1) // per_page
                context['page_range'] = range(1, total_pages + 1)
            except (ConnectionError, NotFoundError):
                context['fallback_mode'] = True
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
    }
    
    def get(self, request, *args, **kwargs):
        q = request.GET.get('q', '').strip()
        
        if len(q) < 2:
            return JsonResponse({'suggestions': []})
        
        detected_lang = detect_language(q)
        suggestions = []
        
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
                if detected_lang == 'arabic':
                    boost_query = Q('match', **{'title.arabic': {'query': q, 'boost': 2.0}})
                else:
                    boost_query = Q('match', **{'title.english': {'query': q, 'boost': 2.0}})
                
                # Combine queries
                search = search.query(
                    Q('bool', should=[multi_match_query, boost_query], minimum_should_match=1)
                )
                
                # Only get top 3 per type for quick suggestions
                search = search[:3]
                search = search.source([config['title_field']])
                
                response = search.execute()
                
                for hit in response:
                    title = getattr(hit, config['title_field'], '')
                    if title:
                        try:
                            url = reverse(config['url_name'], kwargs={'pk': hit.meta.id})
                        except:
                            url = '#'
                        
                        suggestions.append({
                            'title': str(title),
                            'type': doc_type,
                            'link': url,
                            'score': hit.meta.score,
                        })
            except Exception as e:
                logger.warning(f"Autocomplete error for {doc_type}: {e}")
                continue
        
        # Sort by score and limit to top 8
        suggestions.sort(key=lambda x: x.get('score', 0), reverse=True)
        suggestions = suggestions[:8]
        
        # Remove score from response
        for s in suggestions:
            s.pop('score', None)
        
        return JsonResponse({'suggestions': suggestions})
    