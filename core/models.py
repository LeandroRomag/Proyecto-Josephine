from django.db import models


class SiteSettings(models.Model):
    site_name = models.CharField(max_length=200, default='Josephine Shop')
    contact_whatsapp = models.CharField(max_length=50, blank=True)

    def __str__(self):
        return self.site_name


class SiteText(models.Model):
    """Key/value store for editable site texts displayed in templates.

    Example keys: 'footer_help_title', 'hero_headline', 'marquee_text',
    'footer_help_links' (could be JSON or plain text), etc.
    """
    key = models.SlugField(max_length=100, unique=True)
    text = models.TextField(blank=True)
    description = models.CharField(max_length=255, blank=True, help_text='(admin only) short note about the purpose of this text')

    class Meta:
        verbose_name = 'Site text'
        verbose_name_plural = 'Site texts'

    def __str__(self):
        return self.key
