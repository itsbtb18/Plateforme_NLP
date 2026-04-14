from django.db.models.signals import pre_save
from django.dispatch import receiver

from scraping.models import ScrapingSource


@receiver(pre_save, sender=ScrapingSource)
def remember_previous_source_url(sender, instance, **kwargs):
    """Store effective URL before save to detect URL changes in post_save."""
    if not instance.pk:
        instance._previous_effective_url = ""  # noqa: SLF001
        return

    previous = sender.objects.filter(pk=instance.pk).values("url", "base_url").first()
    if previous:
        instance._previous_effective_url = (
            previous.get("url") or previous.get("base_url") or ""
        ).strip()  # noqa: SLF001
    else:
        instance._previous_effective_url = ""  # noqa: SLF001


# DISABLED: manual-only mode
# This was auto-triggering scraping on model save
# Re-enable only if scheduled scraping is needed
# @receiver(post_save, sender=ScrapingSource)
# def auto_validate_on_save(sender, instance, created, **kwargs):
#     """Trigger async source validation after create or URL change."""
#     if getattr(settings, "SCRAPING_MANUAL_ONLY", False):
#         return
#
#     if not getattr(settings, "SCRAPING_AUTO_VALIDATE_ON_SAVE", True):
#         return
#
#     current_effective_url = (instance.url or instance.base_url or "").strip()
#     previous_effective_url = getattr(instance, "_previous_effective_url", "").strip()
#
#     if not current_effective_url:
#         return
#
#     if created or current_effective_url != previous_effective_url:
#         sender.objects.filter(pk=instance.pk).update(validation_status="PENDING")
#         validate_source_async.delay(str(instance.id))
