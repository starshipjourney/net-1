from django.shortcuts        import render, get_object_or_404, redirect
from django.contrib.auth.decorators import login_required
from django.contrib.auth.models     import User
from django.http                    import JsonResponse, HttpResponseForbidden
from django.views.decorators.http   import require_POST
from django.db.models               import Q, Count, Max
import json

from .models import Note, NoteTag, NoteShare, NoteImage, NoteComment, NotePersonalTag


# ============================================================
#  NOTES DECK — card grid
# ============================================================
@login_required
def notes_deck(request):
    user = request.user

    # base queryset — all notes visible to this user
    own_notes    = Note.objects.filter(author=user)
    public_notes = Note.objects.filter(visibility='public').exclude(author=user)
    shared_notes = Note.objects.filter(
        visibility='shared',
        shares__shared_with=user
    ).exclude(author=user)

    base_notes = (own_notes | public_notes | shared_notes).distinct()

    # tag filter
    tag_filter = request.GET.get('tag', '').strip()

    # visibility filter
    vis_filter = request.GET.get('vis', '').strip()

    # search filter
    search = request.GET.get('q', '').strip()

    # sort
    sort = request.GET.get('sort', 'updated').strip()

    SORT_MAP = {
        'updated'  : '-updated_at',
        'oldest'   : 'updated_at',
        'created'  : '-created_at',
        'title_asc': 'title',
        'title_desc': '-title',
        'author'   : 'author__username',
        'comments' : '-comment_count',
        'pinned'   : '-pinned',
    }

    order_field = SORT_MAP.get(sort, '-updated_at')

    if sort == 'comments':
        all_notes = base_notes.annotate(comment_count=Count('comments')).order_by(order_field)
    elif sort == 'pinned':
        all_notes = base_notes.order_by('-pinned', '-updated_at')
    else:
        all_notes = base_notes.order_by(order_field)

    if tag_filter == '__untagged__':
        personally_tagged_ids = NotePersonalTag.objects.filter(
            assigned_by=user
        ).values_list('note_id', flat=True)
        all_notes = all_notes.filter(tags__isnull=True).exclude(
            id__in=personally_tagged_ids
        )
    elif tag_filter:
        author_tagged   = Q(tags__name=tag_filter)
        personal_tagged = Q(
            personal_tags__tag__name=tag_filter,
            personal_tags__assigned_by=user
        )
        all_notes = all_notes.filter(author_tagged | personal_tagged).distinct()

    if vis_filter == 'shared':
        all_notes = all_notes.filter(visibility='shared')
    elif vis_filter == 'public':
        all_notes = all_notes.filter(visibility='public')

    if search:
        all_notes = all_notes.filter(
            Q(title__icontains=search) | Q(body_html__icontains=search)
        )

    user_tags = NoteTag.objects.filter(created_by=user)

    sidebar_tags = (
        NoteTag.objects
        .filter(created_by=user)
        .annotate(
            author_count  = Count('notes', distinct=True,
                                  filter=Q(notes__in=base_notes)),
            personal_count= Count('personal_assignments', distinct=True,
                                  filter=Q(personal_assignments__assigned_by=user,
                                           personal_assignments__note__in=base_notes)),
            last_updated  = Max('notes__updated_at',
                                filter=Q(notes__in=base_notes)),
        )
        .order_by('name')
    )

    for tag in sidebar_tags:
        tag.note_count = tag.author_count + tag.personal_count

    personally_tagged_ids = NotePersonalTag.objects.filter(
        assigned_by=user
    ).values_list('note_id', flat=True)
    untagged_qs           = base_notes.filter(tags__isnull=True).exclude(
        id__in=personally_tagged_ids
    )
    untagged_count        = untagged_qs.count()
    untagged_last_updated = untagged_qs.aggregate(last=Max('updated_at'))['last']

    shared_count = base_notes.filter(visibility='shared').count()
    public_count = base_notes.filter(visibility='public').count()

    return render(request, 'notes/deck.html', {
        'notes'                : all_notes,
        'user_tags'            : user_tags,
        'sidebar_tags'         : sidebar_tags,
        'tag_filter'           : tag_filter,
        'vis_filter'           : vis_filter,
        'search'               : search,
        'sort'                 : sort,
        'untagged_count'       : untagged_count,
        'untagged_last_updated': untagged_last_updated,
        'total_count'          : base_notes.count(),
        'shared_count'         : shared_count,
        'public_count'         : public_count,
    })


# ============================================================
#  CREATE NOTE
# ============================================================
@login_required
def note_create(request):
    user     = request.user
    user_tags = NoteTag.objects.filter(created_by=user)

    if request.method == 'POST':
        title      = request.POST.get('title', '').strip()
        body       = request.POST.get('body', '')
        body_html  = request.POST.get('body_html', '')
        visibility = request.POST.get('visibility', 'private')
        tag_ids    = request.POST.getlist('tags')
        pinned     = request.POST.get('pinned') == 'on'

        if not title:
            return render(request, 'notes/edit.html', {
                'error'    : 'Title is required.',
                'user_tags': user_tags,
                'mode'     : 'create',
            })

        note = Note.objects.create(
            title      = title,
            body       = body,
            body_html  = body_html,
            author     = user,
            visibility = visibility,
            pinned     = pinned,
        )

        if tag_ids:
            tags = NoteTag.objects.filter(id__in=tag_ids, created_by=user)
            note.tags.set(tags)

        return redirect('note_detail', note_id=note.id)

    return render(request, 'notes/edit.html', {
        'user_tags': user_tags,
        'mode'     : 'create',
    })


# ============================================================
#  NOTE DETAIL
# ============================================================
@login_required
def note_detail(request, note_id):
    note = get_object_or_404(Note, id=note_id)

    if not note.is_accessible_by(request.user):
        return HttpResponseForbidden()

    comments      = note.comments.select_related('author').all()
    shared_with   = note.shares.select_related('shared_with').all()
    all_users     = User.objects.exclude(id=request.user.id).exclude(
        id__in=note.shares.values_list('shared_with_id', flat=True)
    ) if note.author == request.user else []

    is_owner = note.author == request.user

    personal_tags = NotePersonalTag.objects.filter(
        note        = note,
        assigned_by = request.user,
    ).select_related('tag') if not is_owner else []

    user_tags = NoteTag.objects.filter(created_by=request.user) if not is_owner else []

    assigned_tag_ids = [pt.tag.id for pt in personal_tags]

    return render(request, 'notes/detail.html', {
        'note'            : note,
        'comments'        : comments,
        'shared_with'     : shared_with,
        'all_users'       : all_users,
        'is_owner'        : is_owner,
        'personal_tags'   : personal_tags,
        'user_tags'       : user_tags,
        'assigned_tag_ids': assigned_tag_ids,
    })


# ============================================================
#  EDIT NOTE
# ============================================================
@login_required
def note_edit(request, note_id):
    note      = get_object_or_404(Note, id=note_id, author=request.user)
    user_tags = NoteTag.objects.filter(created_by=request.user)
    all_users = User.objects.exclude(id=request.user.id)
    shared_with_ids = note.shares.values_list('shared_with__id', flat=True)

    if request.method == 'POST':
        note.title      = request.POST.get('title', note.title).strip()
        note.body       = request.POST.get('body', note.body)
        note.body_html  = request.POST.get('body_html', note.body_html)
        note.visibility = request.POST.get('visibility', note.visibility)
        note.pinned     = request.POST.get('pinned') == 'on'
        note.save()

        tag_ids = request.POST.getlist('tags')
        tags    = NoteTag.objects.filter(id__in=tag_ids, created_by=request.user)
        note.tags.set(tags)

        share_users = request.POST.getlist('share_with')
        if note.visibility == 'shared':
            note.shares.all().delete()
            for username in share_users:
                try:
                    u = User.objects.get(username=username)
                    NoteShare.objects.get_or_create(note=note, shared_with=u)
                except User.DoesNotExist:
                    pass

        return redirect('note_detail', note_id=note.id)

    return render(request, 'notes/edit.html', {
        'note'           : note,
        'user_tags'      : user_tags,
        'all_users'      : all_users,
        'shared_with_ids': list(shared_with_ids),
        'mode'           : 'edit',
    })


# ============================================================
#  DELETE NOTE
# ============================================================
@login_required
@require_POST
def note_delete(request, note_id):
    note = get_object_or_404(Note, id=note_id, author=request.user)
    note.delete()
    return redirect('notes_deck')


# ============================================================
#  ADD COMMENT
# ============================================================
@login_required
@require_POST
def note_comment(request, note_id):
    note = get_object_or_404(Note, id=note_id)

    if not note.is_accessible_by(request.user):
        return HttpResponseForbidden()

    body = request.POST.get('body', '').strip()
    if body:
        NoteComment.objects.create(
            note   = note,
            author = request.user,
            body   = body,
        )

    return redirect('note_detail', note_id=note.id)


# ============================================================
#  SHARE NOTE
# ============================================================
@login_required
@require_POST
def note_share(request, note_id):
    note = get_object_or_404(Note, id=note_id, author=request.user)

    action   = request.POST.get('action')
    username = request.POST.get('username', '').strip()

    if action == 'add' and username:
        try:
            user = User.objects.get(username=username)
            if user != request.user:
                NoteShare.objects.get_or_create(note=note, shared_with=user)
                note.visibility = 'shared'
                note.save()
        except User.DoesNotExist:
            pass

    elif action == 'remove':
        user_id = request.POST.get('user_id')
        NoteShare.objects.filter(note=note, shared_with_id=user_id).delete()
        if not note.shares.exists() and note.visibility == 'shared':
            note.visibility = 'private'
            note.save()

    elif action == 'set_visibility':
        vis = request.POST.get('visibility')
        if vis in ('private', 'shared', 'public'):
            note.visibility = vis
            note.save()

    return redirect('note_detail', note_id=note.id)


# ============================================================
#  PIN / UNPIN
# ============================================================
@login_required
@require_POST
def note_pin(request, note_id):
    note        = get_object_or_404(Note, id=note_id, author=request.user)
    note.pinned = not note.pinned
    note.save()
    return JsonResponse({'pinned': note.pinned})


# ============================================================
#  IMAGE UPLOAD
# ============================================================
@login_required
@require_POST
def image_upload(request):
    note_id = request.POST.get('note_id')
    image   = request.FILES.get('image')

    if not image:
        return JsonResponse({'error': 'No image provided'}, status=400)

    note = None
    if note_id:
        try:
            note = Note.objects.get(id=note_id, author=request.user)
        except Note.DoesNotExist:
            pass

    note_image = NoteImage.objects.create(
        note        = note,
        image       = image,
        uploaded_by = request.user,
    )

    return JsonResponse({'url': note_image.image.url})


# ============================================================
#  PERSONAL TAG ASSIGNMENT (AJAX)
# ============================================================
@login_required
@require_POST
def note_personal_tags(request, note_id):
    note = get_object_or_404(Note, id=note_id)

    if not note.is_accessible_by(request.user):
        return HttpResponseForbidden()

    action = request.POST.get('action')
    tag_id = request.POST.get('tag_id')

    if not tag_id:
        return JsonResponse({'error': 'tag_id required'}, status=400)

    tag = get_object_or_404(NoteTag, id=tag_id, created_by=request.user)

    if action == 'add':
        NotePersonalTag.objects.get_or_create(
            note        = note,
            tag         = tag,
            assigned_by = request.user,
        )
    elif action == 'remove':
        NotePersonalTag.objects.filter(
            note        = note,
            tag         = tag,
            assigned_by = request.user,
        ).delete()

    current = NotePersonalTag.objects.filter(
        note        = note,
        assigned_by = request.user,
    ).select_related('tag')

    return JsonResponse({
        'tags': [
            {'id': pt.tag.id, 'name': pt.tag.name,
             'color': pt.tag.color, 'icon': pt.tag.icon}
            for pt in current
        ]
    })


# ============================================================
#  CREATE TAG (AJAX)
# ============================================================
@login_required
@require_POST
def tag_create(request):
    name  = request.POST.get('name', '').strip()
    color = request.POST.get('color', '#f59e0b').strip()

    if not name:
        return JsonResponse({'error': 'Name required'}, status=400)

    icon  = request.POST.get('icon', '🏷️').strip()

    tag, created = NoteTag.objects.get_or_create(
        name       = name,
        created_by = request.user,
        defaults   = {'color': color, 'icon': icon},
    )

    return JsonResponse({
        'id'     : tag.id,
        'name'   : tag.name,
        'color'  : tag.color,
        'icon'   : tag.icon,
        'created': created,
    })


# ============================================================
#  EDIT TAG (AJAX)
# ============================================================
@login_required
@require_POST
def tag_edit(request, tag_id):
    tag = get_object_or_404(NoteTag, id=tag_id, created_by=request.user)

    try:
        data  = json.loads(request.body)
    except json.JSONDecodeError:
        # fallback to POST form data
        data = request.POST

    name  = data.get('name', '').strip()
    color = data.get('color', tag.color).strip()
    icon  = data.get('icon', tag.icon).strip()

    if not name:
        return JsonResponse({'error': 'Name required'}, status=400)

    if NoteTag.objects.filter(
        name=name, created_by=request.user
    ).exclude(id=tag_id).exists():
        return JsonResponse({'error': 'A tag with that name already exists'}, status=400)

    tag.name  = name
    tag.color = color
    tag.icon  = icon
    tag.save()

    return JsonResponse({
        'id'   : tag.id,
        'name' : tag.name,
        'color': tag.color,
        'icon' : tag.icon,
    })


# ============================================================
#  DELETE TAG (AJAX)
# ============================================================
@login_required
@require_POST
def tag_delete(request, tag_id):
    tag = get_object_or_404(NoteTag, id=tag_id, created_by=request.user)

    note_count = tag.notes.count() + tag.personal_assignments.filter(
        assigned_by=request.user
    ).count()

    tag.delete()
    return JsonResponse({'ok': True, 'removed_from': note_count})


# ============================================================
#  PDF EXPORT
# ============================================================
@login_required
def note_pdf(request, note_id):
    from django.template.loader import render_to_string
    from django.http import HttpResponse
    try:
        import weasyprint
    except ImportError:
        return HttpResponse('WeasyPrint not installed.', status=500)

    note = get_object_or_404(Note, id=note_id)
    if not note.is_accessible_by(request.user):
        return HttpResponseForbidden()

    html_string = render_to_string('notes/pdf.html', {
        'note'     : note,
        'base_url' : request.build_absolute_uri('/'),
    })
    pdf_file = weasyprint.HTML(
        string   = html_string,
        base_url = request.build_absolute_uri('/'),
    ).write_pdf()

    response = HttpResponse(pdf_file, content_type='application/pdf')
    safe_title = note.title.replace(' ', '_')[:60]
    response['Content-Disposition'] = f'attachment; filename="{safe_title}.pdf"'
    return response


# ============================================================
#  REFERENCE SEARCH
# ============================================================
@login_required
def ref_search(request):
    from data_master.models import Document
    query = request.GET.get('q', '').strip()
    if not query or len(query) < 2:
        return JsonResponse({'results': []})

    results = Document.objects.filter(
        Q(title__icontains=query) | Q(summary__icontains=query),
        is_active=True
    ).order_by('source_type', 'title')[:20]

    return JsonResponse({
        'results': [
            {
                'id'         : doc.id,
                'title'      : doc.title,
                'author'     : doc.author or '',
                'source_type': doc.source_type,
                'slug'       : doc.slug,
                'summary'    : (doc.summary or '')[:300],
                'full_text'  : (doc.full_text or '')[:8000],
            }
            for doc in results
        ]
    })