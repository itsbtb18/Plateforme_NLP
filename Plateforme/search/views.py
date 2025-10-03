import re
from django.http import JsonResponse
from django.shortcuts import render
from django.views import View
from django.core.paginator import Paginator, PageNotAnInteger, EmptyPage
from elasticsearch_dsl import Q,MultiSearch 
from elasticsearch_dsl.query import  MultiMatch, DisMax, Bool, Term, MatchPhrase
import logging

from .documents import (
    CourseDocument, InstitutionDocument, ResourceDocument, ProjectDocument,
    EventDocument, ToolDocument, CorpusDocument, UserDocument
)

logger = logging.getLogger(__name__)

class GlobalSearchView(View):
    template_name = 'search/search_results.html'
    RESULTS_PER_PAGE = 12
    DOCUMENT_FIELDS = {
        'course': {
            'multilingual': [
                'title^3', 
                'title.raw^3.5',
                'description^2',
                'description.raw^2.5',
                'keywords^2',
                'keywords.raw^2.5',
                'field.raw^2.5',
                'field^2',
                'field_display.raw^2.5',
                'field_display^2',
                'academic_level.raw^2',
                'academic_level^1.5',
                'academic_level_display.raw^2',
                'academic_level_display^1.5',
                'language.raw^2',
                'language^1.5',
                'language_display.raw^2',
                'language_display^1.5',
                'institution_name^2.5',
                'institution_name.raw^3',
                'institution_acronym^2',
                'institution_acronym.raw^2.5'
            ],
            'english': [
                'title.english^3.5',
                'description.english^2.5',
                'keywords.english^2',
                'field.english^2',
                'field_display.english^2',
                'academic_level.english^1.5',
                'academic_level_display.english^1.5',
                'language.english^1.5',
                'language_display.english^1.5',
                'institution_name.english^2.5',
                'institution_acronym.english^2'
            ],
            'arabic': [
                'title.arabic^3.5',
                'description.arabic^2.5',
                'keywords.arabic^2',
                'field.arabic^2',
                'field_display.arabic^2',
                'academic_level.arabic^1.5',
                'academic_level_display.arabic^1.5',
                'language.arabic^1.5',
                'language_display.arabic^1.5'
            ],
            'phonetic': [
                'title.phonetic^3',
                'keywords.phonetic^2',
                'field.phonetic^2',
                'field_display.phonetic^2'
            ]
        },
        'corpus': {
            'multilingual': [
                'title^3', 
                'title.raw^3.5',
                'description^2',
                'description.raw^2.5',
                'keywords^2',
                'keywords.raw^2.5',
                'field.raw^2.5',
                'field^2',
                'field_display.raw^2.5',
                'field_display^2',
                'language.raw^2',
                'language^1.5',
                'language_display.raw^2',
                'language_display^1.5'
            ],
            'english': [
                'title.english^3.5',
                'description.english^2.5',
                'keywords.english^2',
                'field.english^2',
                'field_display.english^2',
                'language.english^1.5',
                'language_display.english^1.5'
            ],
            'arabic': [
                'title.arabic^3.5',
                'description.arabic^2.5',
                'keywords.arabic^2',
                'field.arabic^2',
                'field_display.arabic^2',
                'language.arabic^1.5',
                'language_display.arabic^1.5'
            ],
            'phonetic': [
                'title.phonetic^2',
                'description.phonetic^1.5',
                'keywords.phonetic^1.5',
                'field.phonetic^2',
                'field_display.phonetic^2'
            ]
        },
        'tool': {
            'multilingual': [
                'title^3',
                'title.raw^3.5', 
                'description^2',
                'description.raw^2.5',
                'keywords^2',
                'keywords.raw^2.5',
                'tool_type.raw^2.5',
                'tool_type^2',
                'get_tool_type_display^2.5',
                'type_type_display.raw^2.5',
                'type_type_display^2',
                'version^1.5',
                'language.raw^2',
                'language^1.5',
                'language_display.raw^2',
                'language_display^1.5',
                'supported_languages^1.5'
            ],
            'english': [
                'title.english^3.5',
                'description.english^2.5',
                'keywords.english^2',
                'tool_type.english^2',
                'type_type_display.english^2.5',
                'language.english^1.5',
                'language_display.english^1.5'
            ],
            'arabic': [
                'title.arabic^3.5',
                'description.arabic^2.5',
                'keywords.arabic^2',
                'tool_type.arabic^2',
                'type_type_display.arabic^2.5',
                'language.arabic^1.5',
                'language_display.arabic^1.5'
            ],
            'phonetic': [
                'title.phonetic^2',
                'description.phonetic^1.5',
                'keywords.phonetic^1.5'
            ]
        },
        'resource': {
            'multilingual': [
                'title^3',
                'title.raw^3.5',
                'description^2',
                'description.raw^2.5',
                'keywords^2',
                'keywords.raw^2.5',
                'document_type.raw^4',
                'document_type^3.5',
                'document_type_display.raw^4',
                'document_type_display^3.5',
                'subtype_fields.supervisor^2',
                'subtype_fields.journal^2',
                'subtype_fields.academic_level^2',
                'subtype_fields.institution^1.5'
            ],
            'english': [
                'title.english^3.5',
                'description.english^2.5',
                'keywords.english^2',
                'document_type.english^3',
                'document_type_display.english^3'
            ],
            'arabic': [
                'title.arabic^3.5',
                'description.arabic^2.5',
                'keywords.arabic^2',
                'document_type.arabic^3',
                'document_type_display.arabic^3'
            ]
        },
        'project': {
            'multilingual': [
                'title^3',
                'title.raw^3.5',
                'description^2',
                'description.raw^2.5',
                'status.raw^2.5',
                'status^2'
            ],
            'english': [
                'title.english^3.5',
                'description.english^2.5',
                'status.english^2'
            ],
            'arabic': [
                'title.arabic^3.5',
                'description.arabic^2.5',
                'status.arabic^2'
            ]
        },
        'event': {
            'multilingual': [
                'title^3',
                'title.raw^3.5',
                'description^2',
                'description.raw^2.5',
                'event_type.raw^2.5',
                'event_type^2',
                'location.raw^2',
                'location^1.5',
                'domains^1.2'
            ],
            'english': [
                'title.english^3.5',
                'description.english^2.5',
                'event_type.english^2',
                'location.english^1.5'
            ],
            'arabic': [
                'title.arabic^3.5',
                'description.arabic^2.5',
                'event_type.arabic^2',
                'location.arabic^1.5'
            ]
        },
        'user': {
            'multilingual': [
                'full_name^3',
                'full_name.raw^3.5',
                'bio^2',
                'email^1.5'
            ]
        },
        'institution': {
            'multilingual': [
                'name^3',
                'name.raw^3.5',
                'acronym^2',
                'acronym.raw^2.5',
                'description^2',
                'description.raw^2.5',
                'country.name^1.5',
                'country.name.raw^2',
                'specialties.name^1.5',
                'specialties.name.raw^2'
            ],
            'english': [
                'name.english^3.5',
                'acronym.english^2.5',
                'description.english^2',
                'country.name.english^1.5',
                'specialties.name.english^1.5'
            ],
            'arabic': [
                'name.arabic^3.5',
                'acronym.arabic^2.5',
                'description.arabic^2',
                'country.name.arabic^1.5',
                'specialties.name.arabic^1.5'
            ],
            'phonetic': [
                'name.phonetic^2',
                'acronym.phonetic^1.5'
            ]
        }
    }
   
    LINK_MAPPING = {
        'course': 'courses',
        'resource': 'resources',
        'project': 'projects',
        'event': 'events',
        'tool': 'tools',
        'corpus': 'corpuses',
        'user': 'accounts/users',
        'institution': 'institutions'
    }

    FIELD_MAP = {
        'project': {
            'timestamp': 'date_start'
        },
        'event': {
            'timestamp': 'start_date'
        },
        'user': {
            'title': 'full_name',
            'description': 'bio'
        },
        'tool': {
            'timestamp': 'creation_date'
        }
    }

    def handle_ajax_search(self, request):
        query = request.GET.get('q', '').strip()
        if not query:
            return JsonResponse({'results': [], 'total': 0})

        try:
            per_type = self._get_per_type(request)
            language = request.GET.get('language', 'auto')
            doc_type = request.GET.get('type', None)
            subtype = request.GET.get('subtype', None)
            
            results, total_count = self._execute_search(query, per_type, language, doc_type, subtype, with_count=True)
            return JsonResponse({
                'results': results[:20],
                'total': total_count
            })
        except Exception as e:
            logger.exception(f"Search error: {str(e)}")
            return JsonResponse({'error': 'Search service error'}, status=500)

    def handle_normal_search(self, request):
        query = request.GET.get('q', '').strip()
        if not query:
            return render(request, self.template_name, {
                'results': [],
                'total': 0,
                'query': query
            })

        try:
            per_type = self._get_per_type(request)
            language = request.GET.get('language', 'auto')
            doc_type = request.GET.get('type', None)
            subtype = request.GET.get('subtype', None)
            page = request.GET.get('page', 1)
            
            search_per_type = max(per_type * 3, 15)
            results, total_count = self._execute_search(query, search_per_type, language, doc_type, subtype, with_count=True)
            
            paginator = Paginator(results, self.RESULTS_PER_PAGE)
            try:
                paginated_results = paginator.page(page)
            except PageNotAnInteger:
                paginated_results = paginator.page(1)
            except EmptyPage:
                paginated_results = paginator.page(paginator.num_pages)
            
            context = {
                'results': paginated_results,
                'query': query,
                'total': total_count,
                'total_pages': paginator.num_pages,
                'current_page': paginated_results.number,
                'has_previous': paginated_results.has_previous(),
                'has_next': paginated_results.has_next(),
                'previous_page': paginated_results.previous_page_number() if paginated_results.has_previous() else None,
                'next_page': paginated_results.next_page_number() if paginated_results.has_next() else None,
                'page_range': self._get_page_range(paginator, paginated_results.number),
                'filters': {
                    'language': language,
                    'doc_type': doc_type,
                    'subtype': subtype,
                    'per_type': per_type
                }
            }
            
            return render(request, self.template_name, context)
        except Exception as e:
            logger.exception(f"Search error: {str(e)}")
            return render(request, self.template_name, {
                'error': 'An error occurred while searching',
                'query': query,
                'total': 0
            })

    def _get_page_range(self, paginator, current_page):
        total_pages = paginator.num_pages
        if total_pages <= 7:
            return range(1, total_pages + 1)
        
        if current_page <= 4:
            return list(range(1, 6)) + ['...', total_pages]
        elif current_page >= total_pages - 3:
            return [1, '...'] + list(range(total_pages - 4, total_pages + 1))
        else:
            return [1, '...'] + list(range(current_page - 1, current_page + 2)) + ['...', total_pages]

    def _execute_search(self, query, per_type, language='auto', doc_type=None, subtype=None, with_count=False):
        documents = [
            ('course', CourseDocument),
            ('resource', ResourceDocument),
            ('project', ProjectDocument),
            ('event', EventDocument),
            ('tool', ToolDocument),
            ('corpus', CorpusDocument),
            ('user', UserDocument),
            ('institution', InstitutionDocument)
        ]

        if doc_type:
            documents = [(t, c) for t, c in documents if t == doc_type]
            if not documents:
                logger.warning(f"Unknown document type: {doc_type}")
                return ([], 0) if with_count else []

        detected_lang = self._detect_language(query) if language == 'auto' else language

        multi_search = MultiSearch()
        total_count = 0
        
        for doc_type, doc_class in documents:
            search = self._build_search(query, doc_type, doc_class, per_type, detected_lang, subtype)
            multi_search = multi_search.add(search)
            
            if with_count:
                try:
                    count_search = self._build_search(query, doc_type, doc_class, 0, detected_lang, subtype)
                    count_response = count_search.count()
                    total_count += count_response
                except Exception as e:
                    logger.error(f"Error counting {doc_type}: {str(e)}")

        try:
            responses = multi_search.execute()
        except Exception as e:
            logger.error(f"Elasticsearch error: {str(e)}")
            return ([], 0) if with_count else []

        results = []
        for (doc_type, _), response in zip(documents, responses):
            try:
                results.extend(self._process_response(doc_type, response))
            except Exception as e:
                logger.error(f"Error processing {doc_type} results: {str(e)}")
                continue

        results = sorted(results, key=lambda x: x['score'], reverse=True)
        
        return (results, total_count) if with_count else results

    def _get_link(self, doc_type, doc_id):
        if doc_type == 'user':
            return f"/accounts/profile/{doc_id}/"
        elif doc_type == 'resource':
            return f"/{self.LINK_MAPPING.get(doc_type, 'resources')}/{doc_id}/"
        elif doc_type in ("course", "tool", "corpus"):
            return f"/resources/details/{doc_type}/{doc_id}/"
        else:
            path = self.LINK_MAPPING.get(doc_type, f"{doc_type}s")
            return f"/{path}/{doc_id}/"

    def get(self, request):
        if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
            return self.handle_ajax_search(request)
        return self.handle_normal_search(request)
        
    def _get_per_type(self, request):
        try:
            per_type = int(request.GET.get('per_type', 5))
            return max(min(per_type, 20), 1)
        except ValueError:
            return 5

    def _detect_language(self, query):
        arabic_pattern = re.compile(r'[\u0600-\u06FF\u0750-\u077F\u08A0-\u08FF\uFB50-\uFDFF\uFE70-\uFEFF\u0660-\u0669\u06F0-\u06F9]+')
        if arabic_pattern.search(query):
            return 'ar'
        return 'en'

    def _build_search(self, query, doc_type, doc_class, per_type, detected_lang='en', subtype=None):
        field_config = self.DOCUMENT_FIELDS.get(doc_type, {})
        must_queries = []
        should_queries = []
        default_fields = {
            'multilingual': ['title^3', 'description^2'],
            'english': ['title.english^3', 'description.english^2'],
            'arabic': ['title.arabic^3', 'description.arabic^2'],
            'phonetic': ['title.phonetic^2', 'description.phonetic^1.5']
        }
        fields_to_use = field_config or default_fields

        if doc_type == 'resource' and subtype:
            must_queries.append(Term(document_type=subtype))
        
        if doc_type == 'tool' and subtype:
            must_queries.append(Term(tool_type=subtype))
            
        if doc_type == 'event' and subtype:
            must_queries.append(Term(event_type=subtype))

        if detected_lang == 'ar':
            should_queries.append(
                MultiMatch(
                    query=query,
                    fields=fields_to_use.get('arabic', default_fields['arabic']),
                    type='best_fields',
                    boost=1.5
                )
            )
        elif detected_lang == 'en':
            should_queries.extend([
                MultiMatch(
                    query=query,
                    fields=fields_to_use.get('english', default_fields['english']),
                    type='best_fields',
                    fuzziness='AUTO',
                    boost=2.0
                ),
                MultiMatch(
                    query=query,
                    fields=fields_to_use.get('multilingual', default_fields['multilingual']),
                    type='best_fields',
                    minimum_should_match='75%',
                    boost=1.0
                )
            ])

        must_queries.append(
            MultiMatch(
                query=query,
                fields=fields_to_use.get('multilingual', default_fields['multilingual']),
                type='best_fields',
                tie_breaker=0.3,
                minimum_should_match='75%',
                fuzziness='AUTO',
                boost=1.0
            )
        )

        if subtype:
            if doc_type == 'resource':
                must_queries.append(Term(document_type=subtype))
            elif doc_type == 'tool':
                must_queries.append(Term(tool_type=subtype))
            elif doc_type == 'event':
                must_queries.append(Term(event_type=subtype))

        search_query = Bool(
            must=must_queries if must_queries else None,
            should=should_queries,
            minimum_should_match=1 if should_queries else None
        )
        return doc_class.search().query(search_query)[:per_type]

    def _process_response(self, doc_type, response):
        results = []
    
        for hit in response:
            try:
                source = hit.to_dict()
                field_config = self.FIELD_MAP.get(doc_type, {})

                author_name = 'Anonymous'
                if 'author' in source:
                    if isinstance(source['author'], dict):
                        author_name = (
                            source['author'].get('full_name') or 
                            source['author'].get('email') or 
                            'Anonymous'
                        )
                    elif isinstance(source['author'], str):
                        author_name = source['author']
                elif 'organizer' in source:
                    if isinstance(source['organizer'], dict):
                        author_name = (
                            source['organizer'].get('full_name') or 
                            source['organizer'].get('email') or 
                            'Anonymous'
                        ) 
                    elif isinstance(source['organizer'], str):
                        author_name = source['organizer']

                timestamp = None
                timestamp_field = field_config.get('timestamp', 'creation_date')
                for field in [timestamp_field, 'creation_date', 'update_date', 'date_created', 'date_updated']:
                    if field in source and source[field]:
                        timestamp = source[field]
                        break
                
                result = {
                    'type': doc_type,
                    'id': hit.meta.id,
                    'score': hit.meta.score,
                    'title': str(source.get('title', ''))[:200],
                    'description': str(source.get('description', ''))[:300],
                    'link': self._get_link(doc_type, hit.meta.id),
                    'author': author_name,
                    'timestamp': timestamp,
                }

                if doc_type == 'tool':
                    self._process_tool_fields(hit, source, result)
                elif doc_type == 'course':
                    self._process_course_fields(hit, source, result)
                elif doc_type == 'resource':
                    self._process_resource_fields(hit, source, result)
                elif doc_type == 'event':
                    self._process_event_fields(hit, source, result)
                elif doc_type == 'corpus':
                    self._process_corpus_fields(hit, source, result)
                elif doc_type == 'project':
                    self._process_project_fields(hit, source, result)
                elif doc_type == 'user':
                    self._process_user_fields(hit, source, result)
                elif doc_type == 'institution': 
                    self._process_institution_fields(hit, source, result)

                self._process_common_fields(hit, source, result)
                
                timestamp_field = field_config.get('timestamp', 'creation_date')
                if timestamp_field in source:
                    timestamp = source[timestamp_field]
                    if isinstance(timestamp, str):
                        result['timestamp'] = timestamp
                    elif hasattr(timestamp, 'isoformat'):
                        result['timestamp'] = timestamp.isoformat()
                    else:
                        result['timestamp'] = str(timestamp)

                results.append(result)
                
            except Exception as e:
                logger.error(f"Error processing hit for {doc_type}: {str(e)}")
                continue
                
        return results
    
    def _process_institution_fields(self, hit, source, result):
        if 'type' in source:
            result['institution_type'] = str(source['type'])
            result['title'] = str(source.get('name', ''))
        if 'country' in source and isinstance(source['country'], dict):
            result['country'] = source['country'].get('name', '')
            result['country_code'] = source['country'].get('code', '')
        result['institution_name'] = source.get('name', '')
        if 'city' in source:
            result['city'] = str(source['city'])
        
        if 'acronym' in source:
            result['acronym'] = str(source['acronym'])
        
        if 'specialties' in source:
            if isinstance(source['specialties'], (list, tuple)):
                result['specialties'] = [spec.get('name', '') for spec in source['specialties']]
        
        result['link'] = f"/institutions/{hit.meta.id}/"
    
    def _process_project_fields(self, hit, source, result):
        if 'status' in source:
            result['status'] = str(source['status'])
        
        if 'date_start' in source:
            result['timestamp'] = source['date_start']
        elif 'start_date' in source:
            result['timestamp'] = source['start_date']

    def _process_user_fields(self, hit, source, result):
        if 'full_name' in source:
            result['title'] = str(source['full_name'])

        if 'bio' in source:
            result['description'] = str(source['bio'])[:300]
        
        result['author'] = result['title']
        
        if 'email' in source:
            result['email'] = str(source['email'])
        
        if 'profile_picture' in source:
            result['profile_picture'] = str(source['profile_picture'])
        elif 'avatar' in source:
            result['profile_picture'] = str(source['avatar'])

        result['link'] = f"/accounts/profile/{hit.meta.id}/"

    def _process_course_fields(self, hit, source, result):
        for field in ['academic_level', 'academic_level_display', 'field', 'field_display']:
            if field in source:
                result[field] = str(source[field])
        
        if 'academic_level_display' in source:
            result['academic_level'] = str(source['academic_level_display'])
        elif 'academic_level' in source:
            result['academic_level'] = str(source['academic_level'])
            
        if 'field_display' in source:
            result['field'] = str(source['field_display'])
        elif 'field' in source:
            result['field'] = str(source['field'])

        if 'institution_name' in source:
            result['institution'] = str(source['institution_name'])

    def _process_resource_fields(self, hit, source, result):
        if 'document_type' in source:
            doc_type = str(source['document_type'])
            result['subtype'] = doc_type
            result['document_type'] = doc_type
            result['link'] = f"/resources/details/{doc_type}/{hit.meta.id}"
        
        if 'subtype_fields' in source:
            subtype_fields = source['subtype_fields']
            if isinstance(subtype_fields, dict):
                for key, value in subtype_fields.items():
                    result[f'subtype_{key}'] = str(value)

    def _process_event_fields(self, hit, source, result):
        if 'event_type' in source:
            result['event_type'] = str(source['event_type'])
            result['subtype'] = str(source['event_type'])
        
        if 'location' in source:
            result['location'] = str(source['location'])
        
        if 'domains' in source:
            if isinstance(source['domains'], (list, tuple)):
                result['domains'] = [str(domain) for domain in source['domains']]
            else:
                result['domains'] = [str(source['domains'])]
        
        if 'start_date' in source:
            result['timestamp'] = source['start_date']
        elif 'date_start' in source:
            result['timestamp'] = source['date_start']

    def _process_corpus_fields(self, hit, source, result):
        for field in ['field', 'field_display', 'language', 'language_display']:
            if field in source:
                result[field] = str(source[field])
        
        if 'field_display' in source:
            result['field'] = str(source['field_display'])
        elif 'field' in source:
            result['field'] = str(source['field'])

    def _process_tool_fields(self, hit, source, result):
        if 'tool_type' in source:
            result['tool_type'] = str(source['tool_type'])
            result['subtype'] = str(source['tool_type'])
        
        if 'version' in source:
            result['version'] = str(source['version'])
        
        if 'supported_languages' in source:
            supported_langs = source['supported_languages']
            if isinstance(supported_langs, (list, tuple)):
                result['supported_languages'] = [str(lang) for lang in supported_langs]
            elif isinstance(supported_langs, str):
                result['supported_languages'] = [s.strip() for s in supported_langs.split(',')]
            else:
                result['supported_languages'] = []

        if 'creation_date' in source:
            result['timestamp'] = source['creation_date']
        elif 'date_created' in source:
            result['timestamp'] = source['date_created']

        result['link'] = f"/resources/details/tool/{hit.meta.id}/"

    def _process_common_fields(self, hit, source, result):
        if 'language_display' in source:
            result['language'] = str(source['language_display'])
        elif 'language' in source:
            result['language'] = str(source['language'])

        if 'field_display' in source:
            result['field'] = str(source['field_display'])
        elif 'field' in source:
            result['field'] = str(source['field'])

        if 'academic_level_display' in source:
            result['academic_level'] = str(source['academic_level_display'])
        elif 'academic_level' in source:
            result['academic_level'] = str(source['academic_level'])