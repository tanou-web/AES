from django.urls import path
from . import views

app_name = 'messagerie'

urlpatterns = [
    # Vues principales
    path('', views.conversations_list, name='conversations'),
    path('chat/<uuid:conversation_id>/', views.chat_view, name='chat'),
    path('start/<int:ami_id>/', views.start_conversation, name='start_conversation'),
    
    # Actions sur les messages
    path('send/', views.send_message, name='send_message'),
    path('message/<uuid:message_id>/edit/', views.edit_message, name='edit_message'),
    path('message/<uuid:message_id>/read/', views.mark_message_read, name='mark_read'),
    path('message/<uuid:message_id>/delete/', views.delete_message, name='delete_message'),
    path('message/<uuid:message_id>/forward/', views.forward_message, name='forward_message'),
    
    # Gestion des conversations
    path('conversation/<uuid:conversation_id>/read/', views.mark_conversation_read, name='mark_conversation_read'),
    path('conversation/<uuid:conversation_id>/archive/', views.archive_conversation, name='archive_conversation'),
    path('conversation/<uuid:conversation_id>/messages/', views.get_conversation_messages, name='get_messages'),
    path('conversation/<uuid:conversation_id>/settings/', views.conversation_settings, name='conversation_settings'),
    
    # Réactions
    path('message/<uuid:message_id>/react/', views.add_reaction, name='add_reaction'),
    path('message/<uuid:message_id>/unreact/', views.remove_reaction, name='remove_reaction'),
    
    # Recherche
    path('search/', views.search_messages, name='search_messages'),
]
