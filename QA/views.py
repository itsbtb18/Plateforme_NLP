from django.shortcuts import render, redirect, get_object_or_404
from .models import Question, Post, Comment
from .forms import QuestionForm, AnswerForm, PostForm, CommentForm
from django.db.models import Q, Count
from django.contrib.auth import get_user_model
from notifications.models import Notification
from notifications.services import NotificationService
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.http import JsonResponse
from django.views.decorators.http import require_POST
from django.db import models
from django.urls import reverse
from django.conf import settings

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
                    title="New answer to your question",
                    message=f"{request.user.username} answered your question « {question.title} ».",
                    related_object=question
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
    # Posts populaires (les plus likés)
    popular_posts = Post.objects.annotate(
        like_count=models.Count('likes')
    ).order_by('-like_count', '-created_at')[:5]

    # Posts récents
    recent_posts = Post.objects.order_by('-created_at')[:5]

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
    posts = Post.objects.all()
    post_form = PostForm()
    comment_form = CommentForm()
    return render(request, 'QA/feed.html', {
        'posts': posts,
        'post_form': post_form,
        'comment_form': comment_form,
        'page': 'feed'
    })

@login_required
@login_and_verified_required
def create_post(request):
    if request.method == 'POST':
        form = PostForm(request.POST, request.FILES)
        if form.is_valid():
            post = form.save(commit=False)
            post.author = request.user
            post.save()
            messages.success(request, 'Your post has been successfully created.')
            return redirect('QA:feed')
        
    return redirect('QA:feed')




@login_required
@login_and_verified_required
def post_detail(request, slug):
    post = get_object_or_404(Post, slug=slug)
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
                    title="New reply to your comment",
                    message=f"{request.user.full_name} replied to your comment.",
                    related_object=post
                )
        
        comment.save()
        
        # Notification à l'auteur du post si ce n'est pas le même utilisateur
        if post.author != request.user and not parent_id:
            NotificationService.create_notification(
                recipient=post.author,
                notification_type='comment',
                title="New comment",
                message=f"{request.user.full_name} commented on your post.",
                related_object=post
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
                title="New I like",
                message=f"{request.user.full_name} liked your post.",
                related_object=post
            )
    
    response_data = {
        'liked': liked,
        'total_likes': post.total_likes()
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
                title="New I like",
                message=f"{request.user.full_name} liked your comment.",
                related_object=comment.post
            )
    
    return JsonResponse({
        'liked': liked,
        'total_likes': comment.total_likes()
    })

@login_required
@login_and_verified_required
def delete_post(request, post_id):
    post = get_object_or_404(Post, id=post_id, author=request.user)
    post.delete()
    messages.success(request, 'The post has been deleted.')
    return redirect('QA:feed')

@login_required
@login_and_verified_required
def delete_comment(request, comment_id):
    comment = get_object_or_404(Comment, id=comment_id, author=request.user)
    post_slug = comment.post.slug
    comment.delete()
    messages.success(request, 'The comment has been deleted.')
    return redirect('QA:post_detail', slug=post_slug)

@login_required
@login_and_verified_required
def edit_post(request, post_id):
    post = get_object_or_404(Post, id=post_id, author=request.user)

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

            post = form.save()
            messages.success(request, 'Your post has been successfully edited.')
            return redirect('QA:post_detail', slug=post.slug)
    else:
        form = PostForm(instance=post)

    return render(request, 'QA/edit_post.html', {
        'form': form,
        'post': post , 
        'page': 'feed'
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

