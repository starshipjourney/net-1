from django.db import models
from django.utils.text import slugify


# ============================================================
#  SOURCE — tracks where data came from (dump files, feeds)
# ============================================================
class Source(models.Model):

    SOURCE_TYPES = [
        ('wikipedia', 'Wikipedia'),
        ('gutenberg', 'Project Gutenberg'),
    ]

    name             = models.CharField(max_length=255)
    source_type      = models.CharField(max_length=50, choices=SOURCE_TYPES)
    filename         = models.CharField(max_length=255, blank=True, null=True)
    loaded_at        = models.DateTimeField(auto_now_add=True)
    total_documents  = models.IntegerField(default=0)
    is_active        = models.BooleanField(default=True)
    notes            = models.TextField(blank=True, null=True)

    class Meta:
        ordering = ['-loaded_at']

    def __str__(self):
        return f"{self.name} ({self.source_type})"


# ============================================================
#  DOCUMENT — unified model for all content types
# ============================================================
class Document(models.Model):

    SOURCE_TYPES = [
        ('wikipedia', 'Wikipedia'),
        ('gutenberg', 'Project Gutenberg'),
    ]

    source_type  = models.CharField(max_length=50, choices=SOURCE_TYPES, db_index=True)
    source       = models.ForeignKey(Source, on_delete=models.SET_NULL, null=True, blank=True)
    original_id  = models.CharField(max_length=255, blank=True, null=True)  # original ID from source
    
    title        = models.CharField(max_length=500, db_index=True)
    slug         = models.SlugField(max_length=500, unique=True, db_index=True)
    author       = models.CharField(max_length=255, blank=True, null=True)  # null for wiki
    summary      = models.TextField(blank=True, null=True)
    full_text    = models.TextField(blank=True, null=True)
    categories   = models.TextField(blank=True, null=True)
    language     = models.CharField(max_length=10, default='en')
    last_updated = models.DateTimeField(blank=True, null=True)
    is_active    = models.BooleanField(default=True, db_index=True)

    class Meta:
        ordering = ['title']
        indexes  = [
            models.Index(fields=['source_type', 'is_active']),
            models.Index(fields=['slug']),
            models.Index(fields=['title']),
        ]

    def __str__(self):
        return f"[{self.source_type}] {self.title}"


# ============================================================
#  DOCUMENT REVISION — version control
# ============================================================
class DocumentRevision(models.Model):

    document  = models.ForeignKey(Document, on_delete=models.CASCADE, related_name='revisions')
    source    = models.ForeignKey(Source, on_delete=models.SET_NULL, null=True, blank=True)
    version   = models.IntegerField(default=1)
    diff      = models.TextField(blank=True, null=True)
    previous  = models.ForeignKey('self', on_delete=models.SET_NULL, null=True, blank=True)
    timestamp = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-timestamp']

    def __str__(self):
        return f"{self.document.title} v{self.version}"