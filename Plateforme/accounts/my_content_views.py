"""
User content management view (separated to avoid circular imports)
"""
from django.shortcuts import render
from django.views import View
from accounts.views import LoginAndVerifiedRequiredMixin


class MyContentView(LoginAndVerifiedRequiredMixin, View):
    """
    User dashboard showing all their created content with approval status.
    Shows Pending, Approved, and Rejected content across all models.
    """
    def get(self, request):
        from resources.models import Corpus, NLPTool, Course, Document
        from projects.models import Project
        from forum.models import Topic
        from events.models import Event
        
        user = request.user
        status_filter = request.GET.get('status', 'all')  # all, pending, approved, rejected
        
        # Collect all user's content
        user_content = []
        
        # 1. Resources - Corpus
        for corpus in Corpus.objects.filter(author=user):
            user_content.append({
                'id': corpus.id,
                'type': 'Corpus',
                'type_class': 'corpus',
                'title': corpus.get_localized_title(),
                'created_at': corpus.created_at,
                'approval_status': corpus.approval_status,
                'detail_url': corpus.get_absolute_url() if hasattr(corpus, 'get_absolute_url') else None,
                'edit_url': f'/resources/corpus/{corpus.id}/edit/' if hasattr(corpus, 'get_absolute_url') else None,
            })
        
        # 2. Resources - NLP Tools
        for tool in NLPTool.objects.filter(author=user):
            user_content.append({
                'id': tool.id,
                'type': 'NLP Tool',
                'type_class': 'nlptool',
                'title': tool.get_localized_title(),
                'created_at': tool.created_at,
                'approval_status': tool.approval_status,
                'detail_url': tool.get_absolute_url() if hasattr(tool, 'get_absolute_url') else None,
                'edit_url': f'/resources/tool/{tool.id}/edit/',
            })
        
        # 3. Resources - Courses
        for course in Course.objects.filter(author=user):
            user_content.append({
                'id': course.id,
                'type': 'Course',
                'type_class': 'course',
                'title': course.get_localized_title(),
                'created_at': course.created_at,
                'approval_status': course.approval_status,
                'detail_url': course.get_absolute_url() if hasattr(course, 'get_absolute_url') else None,
                'edit_url': f'/resources/course/{course.id}/edit/',
            })
        
        # 4. Resources - Documents (Articles, Thesis, Memoir)
        for doc in Document.objects.filter(author=user):
            doc_type = doc.get_document_type_display() if hasattr(doc, 'get_document_type_display') else 'Document'
            user_content.append({
                'id': doc.id,
                'type': doc_type,
                'type_class': 'document',
                'title': doc.get_localized_title(),
                'created_at': doc.created_at,
                'approval_status': doc.approval_status,
                'detail_url': doc.get_absolute_url() if hasattr(doc, 'get_absolute_url') else None,
                'edit_url': f'/resources/document/{doc.id}/edit/',
            })
        
        # 5. Projects
        for project in Project.objects.filter(coordinator=user):
            user_content.append({
                'id': project.id,
                'type': 'Project',
                'type_class': 'project',
                'title': project.title,
                'created_at': project.created_at,
                'approval_status': project.approval_status,
                'detail_url': f'/projects/{project.id}/',
                'edit_url': f'/projects/{project.id}/edit/',
            })
        
        # 6. Forum Topics
        for topic in Topic.objects.filter(author=user):
            user_content.append({
                'id': topic.id,
                'type': 'Forum Topic',
                'type_class': 'topic',
                'title': topic.title,
                'created_at': topic.created_at,
                'approval_status': topic.approval_status,
                'detail_url': f'/forum/topic/{topic.id}/',
                'edit_url': f'/forum/topic/{topic.id}/edit/' if hasattr(topic, 'get_absolute_url') else None,
            })
        
        # 7. Events
        for event in Event.objects.filter(created_by=user):
            user_content.append({
                'id': event.id,
                'type': 'Event',
                'type_class': 'event',
                'title': event.title,
                'created_at': event.created_at,
                'approval_status': event.approval_status,
                'detail_url': f'/events/{event.id}/',
                'edit_url': f'/events/{event.id}/edit/',
            })
        
        # Filter by status
        if status_filter != 'all':
            user_content = [item for item in user_content if item['approval_status'] == status_filter]
        
        # Sort by created_at (newest first)
        user_content.sort(key=lambda x: x['created_at'], reverse=True)
        
        # Calculate statistics
        all_content = Corpus.objects.filter(author=user).count() + \
                      NLPTool.objects.filter(author=user).count() + \
                      Course.objects.filter(author=user).count() + \
                      Document.objects.filter(author=user).count() + \
                      Project.objects.filter(coordinator=user).count() + \
                      Topic.objects.filter(author=user).count() + \
                      Event.objects.filter(created_by=user).count()
        
        pending_count = sum(1 for item in user_content if item['approval_status'] == 'pending')
        approved_count = sum(1 for item in user_content if item['approval_status'] == 'approved')
        rejected_count = sum(1 for item in user_content if item['approval_status'] == 'rejected')
        
        stats = {
            'total': len(user_content),
            'all': all_content,
            'pending': pending_count,
            'approved': approved_count,
            'rejected': rejected_count,
        }
        
        context = {
            'user_content': user_content,
            'stats': stats,
            'status_filter': status_filter,
        }
        
        return render(request, 'accounts/my_content.html', context)
