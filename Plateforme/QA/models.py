from django.db import models
from django.conf import settings
from django.utils import timezone
from django.contrib.auth import get_user_model
from django.utils.text import slugify
from django.urls import reverse
import uuid

class Question(models.Model):
    author = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE)
    title = models.CharField(max_length=300)
    description = models.TextField(blank=True)
    created_at = models.DateTimeField(default=timezone.now)

    def __str__(self):
        return self.title

class Answer(models.Model):
    question = models.ForeignKey(Question, related_name='answers', on_delete=models.CASCADE)
    author = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE)
    content = models.TextField()
    created_at = models.DateTimeField(default=timezone.now)

    def __str__(self):
        return f"Réponse par {self.author} à {self.question}"

class Post(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    author = models.ForeignKey(get_user_model(), on_delete=models.CASCADE, related_name='posts')
    content = models.TextField(verbose_name="Contenu")
    image = models.ImageField(upload_to='posts/%Y/%m/%d/', null=True, blank=True, verbose_name="Image")
    file = models.FileField(upload_to='post_files/%Y/%m/%d/', null=True, blank=True, verbose_name="Fichier")
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    likes = models.ManyToManyField(get_user_model(), related_name='liked_posts', blank=True)
    slug = models.SlugField(unique=True, blank=True, max_length=255)

    class Meta:
        ordering = ['-created_at']
        verbose_name = "Publication"
        verbose_name_plural = "Publications"

    def save(self, *args, **kwargs):
        if not self.slug:
            self.slug = slugify(f"{self.author.full_name}-{self.id}")
        super().save(*args, **kwargs)

    def __str__(self):
        return f"Post de {self.author.full_name} - {self.created_at.strftime('%d/%m/%Y')}"

    def get_absolute_url(self):
        return reverse('QA:post_detail', kwargs={'slug': self.slug})

    def total_likes(self):
        return self.likes.count()

    def total_comments(self):
        return self.comments.count()

class Comment(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    post = models.ForeignKey(Post, on_delete=models.CASCADE, related_name='comments')
    author = models.ForeignKey(get_user_model(), on_delete=models.CASCADE, related_name='comments')
    content = models.TextField(verbose_name="Commentaire")
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    likes = models.ManyToManyField(get_user_model(), related_name='liked_comments', blank=True)
    parent = models.ForeignKey('self', on_delete=models.CASCADE, null=True, blank=True, related_name='replies')

    class Meta:
        ordering = ['-created_at']
        verbose_name = "Commentaire"
        verbose_name_plural = "Commentaires"

    def __str__(self):
        return f"Commentaire de {self.author.full_name} sur {self.post}"

    def total_likes(self):
        return self.likes.count()

    def total_replies(self):
        return self.replies.count()
