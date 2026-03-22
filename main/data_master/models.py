from django.db import models
from django.utils.text import slugify
from django.contrib.auth.models import User


# ============================================================
#  SOURCE — tracks where data came from (dump files, feeds)
# ============================================================
class Source(models.Model):

    SOURCE_TYPES = [
        ('wikipedia',  'Wikipedia'),
        ('gutenberg',  'Project Gutenberg'),
        ('wikibooks',  'Wikibooks'),
        ('wikivoyage', 'Wikivoyage'),
        ('ifixit',     'iFixit'),
        ('arxiv',      'arXiv'),
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
        ('wikipedia',  'Wikipedia'),
        ('gutenberg',  'Project Gutenberg'),
        ('wikibooks',  'Wikibooks'),
        ('wikivoyage', 'Wikivoyage'),
        ('ifixit',     'iFixit'),
        ('arxiv',      'arXiv'),
    ]

    source_type  = models.CharField(max_length=50, choices=SOURCE_TYPES, db_index=True)
    source       = models.ForeignKey(Source, on_delete=models.SET_NULL, null=True, blank=True)
    original_id  = models.CharField(max_length=255, blank=True, null=True)

    title        = models.CharField(max_length=500, db_index=True)
    slug         = models.SlugField(max_length=500, unique=True, db_index=True)
    author       = models.CharField(max_length=255, blank=True, null=True)
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


# ============================================================
#  PDF TAG — tag system for PDF library
# ============================================================
class PdfTag(models.Model):
    """
    A tag that can be applied to PDF files.
    Only admin/staff users can create and assign tags.
    Regular users can view and filter by tags.
    """
    name        = models.CharField(max_length=80, unique=True)
    slug        = models.SlugField(max_length=80, unique=True)
    description = models.TextField(blank=True, null=True)
    colour      = models.CharField(max_length=7, default='#f59e0b')
    icon        = models.CharField(max_length=10, default='🏷️')
    created_by  = models.ForeignKey(
        User, on_delete=models.SET_NULL, null=True, related_name='pdf_tags'
    )
    created_at  = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['name']

    def __str__(self):
        return self.name

    def save(self, *args, **kwargs):
        if not self.slug:
            self.slug = slugify(self.name)
        super().save(*args, **kwargs)


# ============================================================
#  PDF TAG ASSIGNMENT — assigns a tag to a PDF file
# ============================================================
class PdfTagAssignment(models.Model):
    """
    Links a PdfTag to a PDF file path.
    pdf_path is the relative path from PDF_DIR.
    """
    tag         = models.ForeignKey(
        PdfTag, on_delete=models.CASCADE, related_name='assignments'
    )
    pdf_path    = models.CharField(max_length=500)
    pdf_name    = models.CharField(max_length=500)
    assigned_by = models.ForeignKey(
        User, on_delete=models.SET_NULL, null=True, related_name='pdf_assignments'
    )
    assigned_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        unique_together = ('tag', 'pdf_path')
        ordering        = ['pdf_name']

    def __str__(self):
        return f'{self.tag.name} → {self.pdf_name}'