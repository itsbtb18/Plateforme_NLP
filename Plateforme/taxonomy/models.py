from django.db import models
from django.utils.translation import gettext_lazy as _


class ResearchDomain(models.Model):
    name_en = models.CharField(max_length=150)
    name_ar = models.CharField(max_length=150)
    slug = models.SlugField(unique=True)
    parent = models.ForeignKey(
        "self",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="children",
    )
    description_en = models.TextField(blank=True, default="")
    description_ar = models.TextField(blank=True, default="")

    class Meta:
        ordering = ["name_en"]
        verbose_name = _("Research Domain")
        verbose_name_plural = _("Research Domains")

    def __str__(self) -> str:
        return self.name_en


class NLPMethod(models.Model):
    name_en = models.CharField(max_length=150)
    name_ar = models.CharField(max_length=150)
    slug = models.SlugField(unique=True)

    class Meta:
        ordering = ["name_en"]
        verbose_name = _("NLP Method")
        verbose_name_plural = _("NLP Methods")

    def __str__(self) -> str:
        return self.name_en


class Dataset(models.Model):
    name = models.CharField(max_length=200)
    huggingface_id = models.CharField(max_length=255, blank=True, null=True)
    paperswithcode_id = models.CharField(max_length=255, blank=True, null=True)
    language = models.CharField(max_length=20, default="ar")
    description_en = models.TextField(blank=True, default="")
    description_ar = models.TextField(blank=True, default="")

    class Meta:
        ordering = ["name"]
        verbose_name = _("Dataset")
        verbose_name_plural = _("Datasets")

    def __str__(self) -> str:
        return self.name

