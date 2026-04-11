import logging

from accounts.blocking import exclude_hidden_users
from django.conf import settings
from django.contrib import messages
from django.contrib.auth import get_user_model
from django.contrib.auth.decorators import login_required, user_passes_test
from django.core.paginator import Paginator
from django.db import models
from django.db.models import Count, Q
from django.http import Http404, JsonResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.utils.translation import gettext_lazy as _
from django.views.decorators.http import require_POST
from notifications.services import LocalizedValue, NotificationService
from pages.moderation import approve_object

from .forms import AnswerForm, CommentForm, PostForm, QuestionForm
from .models import Comment, Post, Question

User = get_user_model()
logger = logging.getLogger(__name__)


def is_admin(user):
    return user.is_staff or user.is_superuser


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
            return redirect(
                settings.LOGIN_URL
            )  # Assurez-vous que settings.LOGIN_URL est configuré

        # Exempter les membres du personnel de la vérification de profil
        if request.user.is_staff:
            return view_func(request, *args, **kwargs)

        if not request.user.is_verified:
            messages.warning(
                request, "Your profile has not yet been verified by an administrator."
            )
            return render(request, "awaiting_verification.html")

        return view_func(request, *args, **kwargs)

    return _wrapped_view_func


def ask_question(request):
    query = request.GET.get("q")
    if request.method == "POST":
        form = QuestionForm(request.POST)
        if form.is_valid():
            title = form.cleaned_data["title"]
            existing = Question.objects.filter(title__icontains=title)
            if existing.exists():
                return render(
                    request, "feed/duplicate_found.html", {"questions": existing}
                )
            question = form.save(commit=False)
            question.author = request.user
            question.save()
            return redirect("feed:question_detail", pk=question.pk)
    else:
        form = QuestionForm()
    return render(request, "feed/ask_question.html", {"form": form})


def question_detail(request, pk):
    question = get_object_or_404(Question, pk=pk)
    answers = question.answers.all()
    if request.method == "POST":
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
                    notification_type="QA_ANSWER",
                    title=_("New answer to your question"),
                    message=_("%(username)s answered your question « %(title)s »."),
                    related_object=question,
                    message_kwargs={
                        "username": request.user.email,
                        "title": question.title,
                    },
                )
            return redirect("feed:question_detail", pk=pk)
    else:
        form = AnswerForm()
    return render(
        request,
        "feed/question_detail.html",
        {"question": question, "answers": answers, "form": form},
    )


def search_questions(request):
    query = request.GET.get("q")
    results = []
    if query:
        results = Question.objects.filter(
            Q(title__icontains=query) | Q(description__icontains=query)
        )
    return render(request, "feed/search.html", {"results": results, "query": query})


def qa_home(request):
    # Posts populaires (les plus likés) - only approved
    popular_posts = (
        exclude_hidden_users(
            Post.objects.filter(approval_status="approved"), request.user, ("author",)
        )
        .annotate(like_count=models.Count("likes"))
        .order_by("-like_count", "-created_at")[:5]
    )

    # Posts récents - only approved
    recent_posts = exclude_hidden_users(
        Post.objects.filter(approval_status="approved"), request.user, ("author",)
    ).order_by("-created_at")[:5]

    # Questions récentes
    recent_questions = Question.objects.order_by("-created_at")[:5]

    # Ressources (posts avec des images)
    resources = exclude_hidden_users(
        Post.objects.exclude(image=""), request.user, ("author",)
    ).order_by("-created_at")[:5]

    context = {
        "popular_posts": popular_posts,
        "recent_posts": recent_posts,
        "recent_questions": recent_questions,
        "resources": resources,
        "page": "feed",
    }

    return render(request, "feed/qa_home.html", context)


@login_required
@login_and_verified_required
def feed(request):
    """Research Feed with filtering and sorting support."""
    from pages.content_parser import extract_paper_metadata

    # Get filter parameter
    filter_type = request.GET.get("filter", "all")

    # Only show approved posts - strict approval workflow
    posts = exclude_hidden_users(
        Post.objects.filter(approval_status="approved"), request.user, ("author",)
    )

    # Apply filters
    if filter_type == "my_posts":
        posts = posts.filter(author=request.user)
    elif filter_type == "popular":
        # Sort by likes count
        posts = posts.annotate(like_count=Count("likes")).order_by(
            "-like_count", "-created_at"
        )
    else:
        # Default: all posts, newest first
        posts = posts.order_by("-created_at")

    paginator = Paginator(posts, 10)
    page_obj = paginator.get_page(request.GET.get("page") or 1)

    for post in page_obj.object_list:
        localized_content = (
            post.get_localized_content()
            if hasattr(post, "get_localized_content")
            else post.content
        )
        # Full abstract (no truncation) for news list
        post.news_meta = extract_paper_metadata(
            localized_content or "", max_abstract_length=None
        )
        # Fallback: use model title/content when parser returns empty (e.g. plain Arabic text)
        if not post.news_meta.get("title"):
            post.news_meta["title"] = (
                post.get_localized_title()
                if hasattr(post, "get_localized_title")
                else (post.title_en or post.title_ar or post.title)
            )
        if not post.news_meta.get("abstract") and localized_content:
            post.news_meta["abstract"] = localized_content

    post_form = PostForm()
    comment_form = CommentForm()

    return render(
        request,
        "feed/feed.html",
        {
            "posts": page_obj,
            "page_obj": page_obj,
            "is_paginated": page_obj.has_other_pages(),
            "post_form": post_form,
            "comment_form": comment_form,
            "page": "feed",
            "current_filter": filter_type,
        },
    )


@login_required
@login_and_verified_required
def create_post(request):
    """Dedicated page for creating a new post."""
    if request.method == "POST":
        form = PostForm(request.POST, request.FILES)
        if form.is_valid():
            try:
                post = form.save(commit=False)
                post.author = request.user
                is_admin_author = request.user.is_staff or request.user.is_superuser
                post.approval_status = "approved" if is_admin_author else "pending"

                logger.info(
                    f"[POST_CREATE] Creating post by user: {request.user.email}, "
                    f"title: {post.get_localized_title()[:50]}"
                )

                post.save()

                if is_admin_author:
                    approve_object(post, moderator=request.user)

                logger.info(
                    f"[POST_CREATE] ✓ Post created successfully "
                    f"(ID: {post.id}, Status: {post.approval_status})"
                )

                if is_admin_author:
                    messages.success(
                        request,
                        _("Your post has been published immediately."),
                    )
                else:
                    messages.info(
                        request,
                        _(
                            "Your post has been submitted and is pending admin approval."
                        ),
                    )
                return redirect("feed:feed")

            except Exception as e:
                logger.error(
                    f"[POST_CREATE] ✗ Error creating post: {str(e)}", exc_info=True
                )
                messages.error(
                    request,
                    _("An error occurred while creating your post. Please try again."),
                )
        else:
            logger.warning(
                f"[POST_CREATE] Form validation failed: {form.errors.as_json()}"
            )
            messages.error(request, _("Please correct the errors in the form."))
    else:
        form = PostForm()

    return render(
        request,
        "feed/create_post.html",
        {
            "form": form,
            "page": "feed",
        },
    )


@login_required
@login_and_verified_required
def post_detail(request, slug):
    from pages.content_parser import extract_paper_metadata

    # Staff/admin can view any post status. Regular users only approved posts.
    base_qs = exclude_hidden_users(Post.objects.all(), request.user, ("author",))
    if request.user.is_staff or request.user.is_superuser:
        post = get_object_or_404(base_qs, slug=slug)
    else:
        post = get_object_or_404(base_qs.filter(approval_status="approved"), slug=slug)

    if (
        not (request.user.is_staff or request.user.is_superuser)
    ) and post.approval_status != "approved":
        raise Http404(_("Post not found."))

    # Extract metadata for News posts (full abstract on detail page)
    localized_content = post.get_localized_content()
    if localized_content:
        post.news_meta = extract_paper_metadata(
            localized_content, max_abstract_length=None
        )
        if not post.news_meta.get("title"):
            post.news_meta["title"] = post.get_localized_title() or post.title
        if not post.news_meta.get("abstract") and localized_content:
            post.news_meta["abstract"] = localized_content
    else:
        post.news_meta = {
            "title": post.get_localized_title() or post.title,
            "all_authors": "",
            "first_author": "",
            "year": "",
            "abstract": "",
            "link": "",
        }
    comment_form = CommentForm()
    return render(
        request,
        "feed/post_detail.html",
        {"post": post, "comment_form": comment_form, "page": "feed"},
    )


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
        parent_id = request.POST.get("parent_id")
        if parent_id:
            parent_comment = get_object_or_404(Comment, id=parent_id, post=post)
            comment.parent = parent_comment

            # Notification à l'auteur du commentaire parent
            if parent_comment.author != request.user:
                NotificationService.create_notification(
                    recipient=parent_comment.author,
                    notification_type="comment_reply",
                    title=_("New reply to your comment"),
                    message=_("%(name)s replied to your comment."),
                    related_object=post,
                    message_kwargs={"name": LocalizedValue.from_user(request.user)},
                )

        comment.save()

        # Notification à l'auteur du post si ce n'est pas le même utilisateur
        if post.author != request.user and not parent_id:
            NotificationService.create_notification(
                recipient=post.author,
                notification_type="comment",
                title=_("New comment"),
                message=_("%(name)s commented on your post."),
                related_object=post,
                message_kwargs={"name": LocalizedValue.from_user(request.user)},
            )

        messages.success(request, "Your comment has been added.")

        if request.headers.get("X-Requested-With") == "XMLHttpRequest":
            return JsonResponse(
                {
                    "status": "success",
                    "comment": {
                        "id": comment.id,
                        "content": comment.content,
                        "author_name": comment.author.full_name,
                        "author_avatar": comment.author.avatar.url
                        if comment.author.avatar
                        else None,
                        "created_at": comment.created_at.strftime("%d/%m/%Y %H:%M"),
                        "is_reply": bool(comment.parent),
                    },
                }
            )

    return redirect("feed:post_detail", slug=post.slug)


@login_required
@require_POST
@login_and_verified_required
def like_post(request, post_id):
    """
    Like or unlike a post.
    POST request only.
    Returns JSON with liked status and total likes count.
    """
    logger.debug("[LIKE] request started post_id=%s user=%s", post_id, request.user)

    # Verify it's a POST request
    if request.method != "POST":
        logger.warning("[LIKE] invalid method=%s", request.method)
        return JsonResponse({"error": "Invalid request method"}, status=405)

    try:
        # Fetch the post by UUID
        post = get_object_or_404(Post, id=post_id)
        logger.debug("[LIKE] post found id=%s", post_id)

        # Check if user already likes the post
        if request.user in post.likes.all():
            logger.debug(
                "[LIKE] removing like user=%s post_id=%s", request.user, post_id
            )
            post.likes.remove(request.user)
            liked = False
        else:
            logger.debug("[LIKE] adding like user=%s post_id=%s", request.user, post_id)
            post.likes.add(request.user)
            liked = True

            # Send notification to post author
            if post.author != request.user:
                NotificationService.create_notification(
                    recipient=post.author,
                    notification_type="like",
                    title=_("New like"),
                    message=_("%(name)s liked your post."),
                    related_object=post,
                    message_kwargs={"name": LocalizedValue.from_user(request.user)},
                )

        # Build response
        response_data = {"liked": liked, "total_likes": post.likes.count()}
        logger.debug(
            "[LIKE] response post_id=%s liked=%s total_likes=%s",
            post_id,
            liked,
            response_data["total_likes"],
        )
        return JsonResponse(response_data)

    except Http404:
        logger.warning("[LIKE] post not found post_id=%s", post_id)
        return JsonResponse({"error": "Post not found"}, status=404)
    except Exception as e:
        logger.exception("[LIKE] unexpected error post_id=%s", post_id)
        return JsonResponse({"error": str(e)}, status=500)


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
                notification_type="like",
                title=_("New like"),
                message=_("%(name)s liked your comment."),
                related_object=comment.post,
                message_kwargs={"name": LocalizedValue.from_user(request.user)},
            )

    return JsonResponse({"liked": liked, "total_likes": comment.total_likes})


@login_required
@login_and_verified_required
def delete_post(request, post_id):
    if request.method != "POST":
        messages.error(request, "Invalid request method.")
        return redirect("feed:feed")
    post = get_object_or_404(Post, id=post_id, author=request.user)
    post.delete()
    messages.success(request, "The post has been deleted.")
    return redirect("feed:feed")


@login_required
@login_and_verified_required
def delete_comment(request, comment_id):
    if request.method != "POST":
        messages.error(request, "Invalid request method.")
        return redirect("feed:feed")
    comment = get_object_or_404(Comment, id=comment_id, author=request.user)
    post_slug = comment.post.slug
    comment.delete()
    messages.success(request, "The comment has been deleted.")
    return redirect("feed:post_detail", slug=post_slug)


@login_required
@login_and_verified_required
def edit_post(request, post_id):
    from pages.content_parser import extract_paper_metadata

    post = get_object_or_404(Post, id=post_id)

    # Check permission: author, staff, or superuser
    is_admin = request.user.is_staff or request.user.is_superuser
    if post.author != request.user and not is_admin:
        messages.error(request, "You do not have permission to edit this post.")
        return redirect("feed:post_detail", slug=post.slug)

    if (not is_admin) and post.approval_status != "approved":
        raise Http404(_("Post not found."))

    # Admin modes
    review_mode = request.GET.get("review") == "1" and is_admin
    edit_only = request.GET.get("edit_only") == "1" and is_admin
    read_only_review = review_mode and not edit_only
    is_pending = post.approval_status == "pending"

    if request.method == "POST":
        if read_only_review:
            messages.warning(
                request,
                _(
                    "This form is read-only in review mode. Use Edit mode to modify fields."
                ),
            )
            return redirect(request.get_full_path())

        form = PostForm(request.POST, request.FILES, instance=post)
        if form.is_valid():
            # Gestion de la suppression d'image
            if form.cleaned_data.get("remove_image") and post.image:
                post.image.delete()
                post.image = None

            # Gestion de la suppression de fichier
            if form.cleaned_data.get("remove_file") and post.file:
                post.file.delete()
                post.file = None

            post = form.save(commit=False)

            # Handle bilingual fields from admin review mode or any admin edit
            if review_mode or is_admin:
                if request.POST.get("title_en") is not None:
                    post.title_en = request.POST.get("title_en", "")
                    post.title = request.POST.get("title_en", post.title) or post.title
                if request.POST.get("title_ar") is not None:
                    post.title_ar = request.POST.get("title_ar", "")
                if request.POST.get("content_en") is not None:
                    post.content_en = request.POST.get("content_en", "")
                if request.POST.get("content_ar") is not None:
                    post.content_ar = request.POST.get("content_ar", "")

            # Handle "Approve & Publish" action
            if request.POST.get("action") == "approve" and is_admin:
                post.approval_status = "approved"
                post.save()
                messages.success(request, _("Post has been approved and published."))
                return redirect("pages:admin_feed")

            post.save()
            messages.success(request, "Your post has been successfully edited.")

            if (
                edit_only
                and request.GET.get("review_model")
                and request.GET.get("review_pk")
            ):
                return redirect(
                    "pages:admin_view_item",
                    model_type=request.GET.get("review_model"),
                    pk=request.GET.get("review_pk"),
                )
            if review_mode:
                return redirect("pages:admin_feed")
            return redirect("feed:post_detail", slug=post.slug)
    else:
        form = PostForm(instance=post)

    localized_content = (
        post.get_localized_content()
        if hasattr(post, "get_localized_content")
        else post.content
    )
    preview_meta = extract_paper_metadata(localized_content or "")

    from pages.content_parser import extract_structured_content

    parsed_en = extract_structured_content(post.content_en or post.content or "")
    parsed_ar = extract_structured_content(post.content_ar or "")

    return render(
        request,
        "feed/edit_post.html",
        {
            "form": form,
            "post": post,
            "page": "feed",
            "review_mode": review_mode,
            "edit_only": edit_only,
            "read_only_review": read_only_review,
            "is_pending": is_pending,
            "preview_meta": preview_meta,
            "is_admin": is_admin,
            "parsed_en": parsed_en,
            "parsed_ar": parsed_ar,
        },
    )


@login_required
@require_POST
@login_and_verified_required
def edit_comment(request, comment_id):
    comment = get_object_or_404(Comment, id=comment_id, author=request.user)
    form = CommentForm(request.POST, instance=comment)

    if form.is_valid():
        comment = form.save()
        if request.headers.get("X-Requested-With") == "XMLHttpRequest":
            return JsonResponse(
                {
                    "status": "success",
                    "comment": {
                        "id": comment.id,
                        "content": comment.content,
                        "author_name": comment.author.full_name,
                        "author_avatar": comment.author.avatar.url
                        if comment.author.avatar
                        else None,
                        "created_at": comment.created_at.strftime("%d/%m/%Y %H:%M"),
                        "is_reply": bool(comment.parent),
                    },
                }
            )
        messages.success(request, "Your comment has been edited.")

    return redirect("feed:post_detail", slug=comment.post.slug)


@login_required
@user_passes_test(is_admin)
def admin_feed_approve(request, post_id):
    """
    Moderation handler moved from pages.views for cleaner feed ownership.
    """
    post = get_object_or_404(Post, id=post_id)
    approve_object(post, moderator=request.user, save=True)
    return redirect("pages:admin_feed")


@login_required
@user_passes_test(is_admin)
def admin_feed_delete(request, post_id):
    """
    Hard-delete feed item from admin panel.
    """
    post = get_object_or_404(Post, id=post_id)
    post.delete()
    return redirect("pages:admin_feed")
