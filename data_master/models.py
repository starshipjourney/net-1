from django.db import models

class WikiDump(models.Model):
    """
    Tracks each dump file loaded into the system.
    Foundation for version control in Phase 2.
    """
    filename        = models.CharField(max_length=255)
    loaded_at       = models.DateTimeField(auto_now_add=True)
    total_pages     = models.IntegerField(default=0)
    is_active       = models.BooleanField(default=True)
    notes           = models.TextField(blank=True)

    class Meta:
        ordering = ['-loaded_at']

    def __str__(self):
        return self.filename


class WikiPage(models.Model):
    """
    Stores each Wikipedia article.
    """
    dump            = models.ForeignKey(WikiDump, on_delete=models.SET_NULL,
                                        null=True, related_name='pages')
    page_id         = models.IntegerField(unique=True)
    title           = models.CharField(max_length=500)
    slug            = models.SlugField(max_length=500, unique=True)
    summary         = models.TextField(blank=True)
    full_text       = models.TextField(blank=True)
    categories      = models.TextField(blank=True)
    last_updated    = models.DateTimeField(null=True, blank=True)
    is_active       = models.BooleanField(default=True)

    class Meta:
        ordering = ['title']
        indexes = [
            models.Index(fields=['title']),
            models.Index(fields=['slug']),
            models.Index(fields=['page_id']),
        ]

    def __str__(self):
        return self.title


class WikiRevision(models.Model):
    """
    Tracks changes between dump loads.
    (version control)
    """
    page            = models.ForeignKey(WikiPage, on_delete=models.CASCADE,
                                        related_name='revisions')
    dump            = models.ForeignKey(WikiDump, on_delete=models.CASCADE,
                                        related_name='revisions')
    version         = models.IntegerField(default=1)
    diff            = models.TextField(blank=True)
    previous        = models.ForeignKey('self', on_delete=models.SET_NULL,
                                        null=True, blank=True)
    timestamp       = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-timestamp']
        unique_together = ['page', 'version']

    def __str__(self):
        return f"{self.page.title} v{self.version}"