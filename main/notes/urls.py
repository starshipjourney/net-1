from django.urls import path
from . import views

urlpatterns = [
    path('',                        views.notes_deck,      name='notes_deck'),
    path('new/',                    views.note_create,     name='note_create'),
    path('<uuid:note_id>/',         views.note_detail,     name='note_detail'),
    path('<uuid:note_id>/edit/',    views.note_edit,       name='note_edit'),
    path('<uuid:note_id>/delete/',  views.note_delete,     name='note_delete'),
    path('<uuid:note_id>/comment/', views.note_comment,    name='note_comment'),
    path('<uuid:note_id>/share/',   views.note_share,      name='note_share'),
    path('<uuid:note_id>/pin/',     views.note_pin,        name='note_pin'),
    path('image/upload/',           views.image_upload,    name='note_image_upload'),
    path('tags/create/',            views.tag_create,      name='tag_create'),
    path('tags/<int:tag_id>/edit/', views.tag_edit,        name='tag_edit'),
    path('tags/<int:tag_id>/delete/', views.tag_delete,    name='tag_delete'),
    path('<uuid:note_id>/pdf/',     views.note_pdf,        name='note_pdf'),
    path('ref/search/',             views.ref_search,      name='note_ref_search'),
    path('<uuid:note_id>/my-tags/', views.note_personal_tags, name='note_personal_tags'),
]