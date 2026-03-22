from django.db import models
from django.contrib.auth.models import User
from django.utils.text import slugify
import uuid


class NoteTag(models.Model):
    name       = models.CharField(max_length=50)
    color      = models.CharField(max_length=7, default='#f59e0b')  # hex color
    icon       = models.CharField(max_length=10, default='🏷️')      # emoji icon
    created_by = models.ForeignKey(User, on_delete=models.CASCADE, related_name='tags')
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        unique_together = ('name', 'created_by')
        ordering        = ['name']

    def __str__(self):
        return self.name


class Note(models.Model):
    VISIBILITY_CHOICES = [
        ('private', 'Private'),
        ('shared',  'Shared with specific users'),
        ('public',  'All users on network'),
    ]

    id         = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    title      = models.CharField(max_length=255)
    body       = models.TextField(blank=True)          # stores Quill delta JSON
    body_html  = models.TextField(blank=True)          # rendered HTML for display
    author     = models.ForeignKey(User, on_delete=models.CASCADE, related_name='notes')
    tags       = models.ManyToManyField(NoteTag, blank=True, related_name='notes')
    visibility = models.CharField(max_length=10, choices=VISIBILITY_CHOICES, default='private')
    pinned     = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['-pinned', '-updated_at']

    def __str__(self):
        return self.title

    def is_accessible_by(self, user):
        if self.author == user:
            return True
        if self.visibility == 'public':
            return True
        if self.visibility == 'shared':
            return self.shares.filter(shared_with=user).exists()
        return False


class NoteShare(models.Model):
    note        = models.ForeignKey(Note, on_delete=models.CASCADE, related_name='shares')
    shared_with = models.ForeignKey(User, on_delete=models.CASCADE, related_name='shared_notes')
    shared_at   = models.DateTimeField(auto_now_add=True)

    class Meta:
        unique_together = ('note', 'shared_with')

    def __str__(self):
        return f"{self.note.title} → {self.shared_with.username}"


class NoteImage(models.Model):
    note       = models.ForeignKey(Note, on_delete=models.CASCADE, related_name='images',
                                   null=True, blank=True)
    image      = models.ImageField(upload_to='note_images/%Y/%m/')
    uploaded_at= models.DateTimeField(auto_now_add=True)
    uploaded_by= models.ForeignKey(User, on_delete=models.SET_NULL, null=True)

    def __str__(self):
        return f"Image for {self.note.title if self.note else 'unattached'}"


class NoteComment(models.Model):
    note       = models.ForeignKey(Note, on_delete=models.CASCADE, related_name='comments')
    author     = models.ForeignKey(User, on_delete=models.CASCADE, related_name='note_comments')
    body       = models.TextField()
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['created_at']

    def __str__(self):
        return f"{self.author.username} on {self.note.title}"


class NotePersonalTag(models.Model):
    """
    Lets any user who can see a note apply their own tags to it
    without affecting the author's tags. Personal to each user.
    """
    note       = models.ForeignKey(Note, on_delete=models.CASCADE, related_name='personal_tags')
    tag        = models.ForeignKey(NoteTag, on_delete=models.CASCADE, related_name='personal_assignments')
    assigned_by= models.ForeignKey(User, on_delete=models.CASCADE, related_name='personal_note_tags')
    assigned_at= models.DateTimeField(auto_now_add=True)

    class Meta:
        unique_together = ('note', 'tag', 'assigned_by')

    def __str__(self):
        return f"{self.assigned_by.username}: {self.tag.name} on {self.note.title}"