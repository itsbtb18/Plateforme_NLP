from django.contrib import admin
from .models import Document, NLPTool, Course , Article, Thesis, Memoir,Corpus 
# Register your models here.
from django.contrib import admin
from .models import Document, Article, Thesis, Memoir

class ArticleInline(admin.StackedInline):
    model = Article
    extra = 1  # Nombre de formulaires vides affichés

class ThesisInline(admin.StackedInline):
    model = Thesis
    extra = 1

class MemoirInline(admin.StackedInline):
    model = Memoir
    extra = 1

@admin.register(Document)
class DocumentAdmin(admin.ModelAdmin):
    # Use the actual field names from your Document model
    list_display = ['title', 'document_type', 'author'] 
    # If you need to show the author's name instead of just the FK
    # Add a method to display author name
    def author_name(self, obj):
        return obj.author.get_full_name() or obj.author.username
    author_name.short_description = 'Author'

    def get_inlines(self, request, obj=None):
        """Affiche uniquement l'inline correspondant au type de document."""
        if obj and obj.type == Document.TypeDocument.ARTICLE:
            return [ArticleInline]
        elif obj and obj.type == Document.TypeDocument.THESE:
            return [ThesisInline]
        elif obj and obj.type == Document.TypeDocument.MEMOIRE:
            return [MemoirInline]
        return []
    
admin.site.register(NLPTool)
admin.site.register(Course)
admin.site.register(Article)
admin.site.register(Thesis)
admin.site.register(Memoir)
admin.site.register(Corpus)
