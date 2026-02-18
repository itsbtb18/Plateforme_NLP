from django.shortcuts import render, redirect, get_object_or_404
from .models import Question, Post, Comment
from .forms import QuestionForm, AnswerForm, PostForm, CommentForm
from django.db.models import Q, Count
from django.contrib.auth import get_user_model
from notifications.models import Notification
from notifications.services import NotificationService, LocalizedValue
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.http import JsonResponse
from django.views.decorators.http import require_POST
from django.db import models
from django.urls import reverse
from django.conf import settings
from django.utils.translation import gettext_lazy as _

User = get_user_model()

def is_verified(user):
    """Check if user profile is verified."""
    return user.is_authenticated and user.is_verified

def login_and_verified_required(view_func):
    """Decorator to check for login and profile verification.
    Staff members are exempt from profile verification check.
    """
    def _wrapped_view_func(request, *args, **kwargs):
        if not request.user.is_authenticated:
            messages.warning(request, "Please log in to access this page.")
            return redirect(settings.LOGIN_URL) # Assurez-vous que settings.LOGIN_URL est configuré

        # Exempter les membres du personnel de la vérification de profil
        if request.user.is_staff:
            return view_func(request, *args, **kwargs)

        if not request.user.is_verified:
             messages.warning(request, "Your profile has not yet been verified by an administrator.")
             return render(request, 'awaiting_verification.html')

        return view_func(request, *args, **kwargs)
    return _wrapped_view_func

def ask_question(request):
    query = request.GET.get('q')
    if request.method == 'POST':
        form = QuestionForm(request.POST)
        if form.is_valid():
            title = form.cleaned_data['title']
            existing = Question.objects.filter(title__icontains=title)
            if existing.exists():
                return render(request, 'QA/duplicate_found.html', {'questions': existing})
            question = form.save(commit=False)
            question.author = request.user
            question.save()
            return redirect('QA:question_detail', pk=question.pk)
    else:
        form = QuestionForm()
    return render(request, 'QA/ask_question.html', {'form': form})

def question_detail(request, pk):
    question = get_object_or_404(Question, pk=pk)
    answers = question.answers.all()
    if request.method == 'POST':
        form = AnswerForm(request.POST)
        if form.is_valid():
            answer = form.save(commit=False)
            answer.author = request.user
            answer.question = question
            answer.save()
            # NOTIFICATION à l'auteur de la question
            if question.author != request.user:
                NotificationService.create_notification(
                    recipient=question.author,
                    notification_type='QA_ANSWER',
                    title=_("New answer to your question"),
                    message=_("%(username)s answered your question « %(title)s »."),
                    related_object=question,
                    message_kwargs={'username': request.user.email, 'title': question.title}
                )
            return redirect('QA:question_detail', pk=pk)
    else:
        form = AnswerForm()
    return render(request, 'QA/question_detail.html', {'question': question, 'answers': answers, 'form': form})

def search_questions(request):
    query = request.GET.get('q')
    results = []
    if query:
        results = Question.objects.filter(
            Q(title__icontains=query) | Q(description__icontains=query)
        )
    return render(request, 'QA/search.html', {'results': results, 'query': query})

def qa_home(request):
    # Posts populaires (les plus likés) - only approved
    popular_posts = Post.objects.filter(approval_status='approved').annotate(
        like_count=models.Count('likes')
    ).order_by('-like_count', '-created_at')[:5]

    # Posts récents - only approved
    recent_posts = Post.objects.filter(approval_status='approved').order_by('-created_at')[:5]

    # Questions récentes
    recent_questions = Question.objects.order_by('-created_at')[:5]

    # Ressources (posts avec des images)
    resources = Post.objects.exclude(image='').order_by('-created_at')[:5]

    context = {
        'popular_posts': popular_posts,
        'recent_posts': recent_posts,
        'recent_questions': recent_questions,
        'resources': resources,
         'page': 'feed'
    }
    
    
    return render(request, 'QA/qa_home.html', context)


@login_required
@login_and_verified_required
def feed(request):
    """Research Feed with filtering and sorting support."""
    # Get filter parameter
    filter_type = request.GET.get('filter', 'all')
    
    # Only show approved posts - strict approval workflow
    posts = Post.objects.filter(approval_status='approved')
    
    # Apply filters
    if filter_type == 'my_posts':
        posts = posts.filter(author=request.user)
    elif filter_type == 'popular':
        # Sort by likes count
        posts = posts.annotate(
            like_count=Count('likes')
        ).order_by('-like_count', '-created_at')
    else:
        # Default: all posts, newest first
        posts = posts.order_by('-created_at')
    
    post_form = PostForm()
    comment_form = CommentForm()
    
    return render(request, 'QA/feed.html', {
        'posts': posts,
        'post_form': post_form,
        'comment_form': comment_form,
        'page': 'feed',
        'current_filter': filter_type,
    })

@login_required
@login_and_verified_required
def create_post(request):
    """Dedicated page for creating a new post."""
    if request.method == 'POST':
        form = PostForm(request.POST, request.FILES)
        if form.is_valid():
            post = form.save(commit=False)
            post.author = request.user
            # All posts require admin approval - no exceptions
            post.approval_status = 'pending'
            post.save()
            messages.info(request, _('Your post has been submitted and is pending admin approval.'))
            return redirect('QA:feed')
    else:
        form = PostForm()
    
    return render(request, 'QA/create_post.html', {
        'form': form,
        'page': 'feed',
    })




@login_required
@login_and_verified_required
def post_detail(request, slug):
    # Only allow viewing approved posts - pending posts only visible in Admin
    post = get_object_or_404(Post, slug=slug, approval_status='approved')
    
    comment_form = CommentForm()
    return render(request, 'QA/post_detail.html', {
        'post': post,
        'comment_form': comment_form,
        'page': 'feed'
    })

@login_required
@require_POST
@login_and_verified_required
def add_comment(request, post_id):
    post = get_object_or_404(Post, id=post_id)
    form = CommentForm(request.POST)
    if form.is_valid():
        comment = form.save(commit=False)
        comment.post = post
        comment.author = request.user
        
        # Gestion des réponses aux commentaires
        parent_id = request.POST.get('parent_id')
        if parent_id:
            parent_comment = get_object_or_404(Comment, id=parent_id, post=post)
            comment.parent = parent_comment
            
            # Notification à l'auteur du commentaire parent
            if parent_comment.author != request.user:
                NotificationService.create_notification(
                    recipient=parent_comment.author,
                    notification_type='comment_reply',
                    title=_("New reply to your comment"),
                    message=_("%(name)s replied to your comment."),
                    related_object=post,
                    message_kwargs={'name': LocalizedValue.from_user(request.user)}
                )
        
        comment.save()
        
        # Notification à l'auteur du post si ce n'est pas le même utilisateur
        if post.author != request.user and not parent_id:
            NotificationService.create_notification(
                recipient=post.author,
                notification_type='comment',
                title=_("New comment"),
                message=_("%(name)s commented on your post."),
                related_object=post,
                message_kwargs={'name': LocalizedValue.from_user(request.user)}
            )
        
        messages.success(request, 'Your comment has been added.')
        
        if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
            return JsonResponse({
                'status': 'success',
                'comment': {
                    'id': comment.id,
                    'content': comment.content,
                    'author_name': comment.author.full_name,
                    'author_avatar': comment.author.avatar.url if comment.author.avatar else None,
                    'created_at': comment.created_at.strftime('%d/%m/%Y %H:%M'),
                    'is_reply': bool(comment.parent)
                }
            })
            
    return redirect('QA:post_detail', slug=post.slug)

@login_required
@require_POST
@login_and_verified_required
def like_post(request, post_id):
    print(f"Like post appelé pour post_id: {post_id}")
    post = get_object_or_404(Post, id=post_id)
    print(f"Post trouvé: {post}")
    
    if request.user in post.likes.all():
        print(f"User {request.user} remove your like")
        post.likes.remove(request.user)
        liked = False
    else:
        print(f"User {request.user} add a like")
        post.likes.add(request.user)
        liked = True
        
        # Notification à l'auteur du post si ce n'est pas le même utilisateur
        if post.author != request.user:
            NotificationService.create_notification(
                recipient=post.author,
                notification_type='like',
                title=_("New like"),
                message=_("%(name)s liked your post."),
                related_object=post,
                message_kwargs={'name': LocalizedValue.from_user(request.user)}
            )
    
    response_data = {
        'liked': liked,
        'total_likes': post.total_likes
    }
    print(f"Response sent: {response_data}")
    return JsonResponse(response_data)

@login_required
@require_POST
@login_and_verified_required
def like_comment(request, comment_id):
    comment = get_object_or_404(Comment, id=comment_id)
    if request.user in comment.likes.all():
        comment.likes.remove(request.user)
        liked = False
    else:
        comment.likes.add(request.user)
        liked = True
        
        # Notification à l'auteur du commentaire si ce n'est pas le même utilisateur
        if comment.author != request.user:
            NotificationService.create_notification(
                recipient=comment.author,
                notification_type='like',
                title=_("New like"),
                message=_("%(name)s liked your comment."),
                related_object=comment.post,
                message_kwargs={'name': LocalizedValue.from_user(request.user)}
            )
    
    return JsonResponse({
        'liked': liked,
        'total_likes': comment.total_likes
    })

@login_required
@login_and_verified_required
def delete_post(request, post_id):
    if request.method != 'POST':
        messages.error(request, 'Invalid request method.')
        return redirect('QA:feed')
    post = get_object_or_404(Post, id=post_id, author=request.user)
    post.delete()
    messages.success(request, 'The post has been deleted.')
    return redirect('QA:feed')

@login_required
@login_and_verified_required
def delete_comment(request, comment_id):
    if request.method != 'POST':
        messages.error(request, 'Invalid request method.')
        return redirect('QA:feed')
    comment = get_object_or_404(Comment, id=comment_id, author=request.user)
    post_slug = comment.post.slug
    comment.delete()
    messages.success(request, 'The comment has been deleted.')
    return redirect('QA:post_detail', slug=post_slug)

@login_required
@login_and_verified_required
def edit_post(request, post_id):
    post = get_object_or_404(Post, id=post_id)
    
    # Check permission: author, staff, or superuser
    is_admin = request.user.is_staff or request.user.is_superuser
    if post.author != request.user and not is_admin:
        messages.error(request, 'You do not have permission to edit this post.')
        return redirect('QA:post_detail', slug=post.slug)
    
    # Admin review mode
    review_mode = request.GET.get('review') == '1' and is_admin
    is_pending = post.approval_status == 'pending'

    if request.method == 'POST':
        form = PostForm(request.POST, request.FILES, instance=post)
        if form.is_valid():
            # Gestion de la suppression d'image
            if form.cleaned_data.get('remove_image') and post.image:
                post.image.delete()
                post.image = None

            # Gestion de la suppression de fichier
            if form.cleaned_data.get('remove_file') and post.file:
                post.file.delete()
                post.file = None

            post = form.save(commit=False)
            
            # Handle bilingual fields from admin review mode
            if review_mode:
                if request.POST.get('title_en'):
                    post.title_en = request.POST.get('title_en', '')
                    post.title = request.POST.get('title_en', post.title)  # Set main title
                if request.POST.get('title_ar'):
                    post.title_ar = request.POST.get('title_ar', '')
                if request.POST.get('content_en'):
                    post.content_en = request.POST.get('content_en', '')
                if request.POST.get('content_ar'):
                    post.content_ar = request.POST.get('content_ar', '')
            
            # Handle "Approve & Publish" action
            if request.POST.get('action') == 'approve' and is_admin:
                post.approval_status = 'approved'
                post.save()
                messages.success(request, _('Post has been approved and published.'))
                return redirect('pages:admin_news')
            
            post.save()
            messages.success(request, 'Your post has been successfully edited.')
            
            if review_mode:
                return redirect('pages:admin_news')
            return redirect('QA:post_detail', slug=post.slug)
    else:
        form = PostForm(instance=post)

    return render(request, 'QA/edit_post.html', {
        'form': form,
        'post': post,
        'page': 'feed',
        'review_mode': review_mode,
        'is_pending': is_pending,
    })

@login_required
@require_POST
@login_and_verified_required
def edit_comment(request, comment_id):
    comment = get_object_or_404(Comment, id=comment_id, author=request.user)
    form = CommentForm(request.POST, instance=comment)
    
    if form.is_valid():
        comment = form.save()
        if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
            return JsonResponse({
                'status': 'success',
                'comment': {
                    'id': comment.id,
                    'content': comment.content,
                    'author_name': comment.author.full_name,
                    'author_avatar': comment.author.avatar.url if comment.author.avatar else None,
                    'created_at': comment.created_at.strftime('%d/%m/%Y %H:%M'),
                    'is_reply': bool(comment.parent)
                }
            })
        messages.success(request, 'Your comment has been edited.')
    
    return redirect('QA:post_detail', slug=comment.post.slug)

