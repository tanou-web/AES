# messagerie/views.py
from django.shortcuts import get_object_or_404, render, redirect
from django.contrib.auth.decorators import login_required
from django.core.paginator import Paginator
from django.http import JsonResponse, Http404, HttpResponseForbidden
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_http_methods
from django.contrib import messages
from django.db.models import Q, Prefetch, Count, Max
from django.core.exceptions import ValidationError
from django.utils import timezone
from django.core.files.storage import default_storage
from django.conf import settings
from django.template.loader import render_to_string
import json
import os
import re

from .models import Message, Conversation, MessageReaction, ConversationSettings
from accounts.models import Etudiant
from relations.models import Relation


# ========== UTILITAIRES ==========

def get_user_etudiant(request):
    """Récupère l'étudiant associé à l'utilisateur connecté"""
    return get_object_or_404(Etudiant, utilisateur=request.user)


def is_mobile_request(request):
    """Détecte si la requête vient d'un appareil mobile"""
    user_agent = request.META.get('HTTP_USER_AGENT', '').lower()
    mobile_keywords = ['mobile', 'android', 'iphone', 'ipad', 'windows phone']
    return any(keyword in user_agent for keyword in mobile_keywords)


def validate_uploaded_file(uploaded_file):
    """Validation renforcée des fichiers uploadés"""
    if not uploaded_file:
        return True, None
    
    # Types de fichiers autorisés avec leurs tailles max
    allowed_types = {
        'image/jpeg': 10 * 1024 * 1024,      # 10MB
        'image/png': 10 * 1024 * 1024,       # 10MB
        'image/gif': 5 * 1024 * 1024,        # 5MB
        'image/webp': 10 * 1024 * 1024,      # 10MB
        'video/mp4': 100 * 1024 * 1024,      # 100MB
        'video/avi': 100 * 1024 * 1024,      # 100MB
        'video/mov': 100 * 1024 * 1024,      # 100MB
        'video/webm': 100 * 1024 * 1024,     # 100MB
        'audio/mp3': 50 * 1024 * 1024,       # 50MB
        'audio/wav': 50 * 1024 * 1024,       # 50MB
        'audio/ogg': 50 * 1024 * 1024,       # 50MB
        'audio/aac': 50 * 1024 * 1024,       # 50MB
        'application/pdf': 25 * 1024 * 1024, # 25MB
        'text/plain': 5 * 1024 * 1024,       # 5MB
        'application/msword': 25 * 1024 * 1024,  # 25MB
        'application/vnd.openxmlformats-officedocument.wordprocessingml.document': 25 * 1024 * 1024,  # 25MB
    }
    
    # Vérifier le type MIME
    if uploaded_file.content_type not in allowed_types:
        return False, f"Type de fichier non autorisé: {uploaded_file.content_type}"
    
    # Vérifier la taille
    max_size = allowed_types[uploaded_file.content_type]
    if uploaded_file.size > max_size:
        max_size_mb = max_size // (1024 * 1024)
        return False, f"Fichier trop volumineux (max {max_size_mb}MB pour ce type)"
    
    # Valider le nom de fichier
    safe_filename = re.sub(r'[^\w\-_\.]', '', uploaded_file.name)
    if not safe_filename or len(safe_filename) > 255:
        return False, "Nom de fichier invalide"
    
    # Vérifier l'extension
    allowed_extensions = {
        'image/jpeg': ['.jpg', '.jpeg'],
        'image/png': ['.png'],
        'image/gif': ['.gif'],
        'image/webp': ['.webp'],
        'video/mp4': ['.mp4'],
        'video/avi': ['.avi'],
        'video/mov': ['.mov'],
        'video/webm': ['.webm'],
        'audio/mp3': ['.mp3'],
        'audio/wav': ['.wav'],
        'audio/ogg': ['.ogg'],
        'audio/aac': ['.aac'],
        'application/pdf': ['.pdf'],
        'text/plain': ['.txt'],
        'application/msword': ['.doc'],
        'application/vnd.openxmlformats-officedocument.wordprocessingml.document': ['.docx'],
    }
    
    file_ext = os.path.splitext(uploaded_file.name)[1].lower()
    valid_extensions = allowed_extensions.get(uploaded_file.content_type, [])
    if file_ext not in valid_extensions:
        return False, f"Extension {file_ext} non valide pour le type {uploaded_file.content_type}"
    
    return True, None


def format_message_for_json(message, user_etudiant):
    """Formate un message pour la réponse JSON"""
    try:
        sender_name = message.sender.get_full_name()
    except:
        try:
            sender_name = message.sender.utilisateur.email
        except:
            sender_name = "Utilisateur"
    
    # Gestion des réactions
    reactions_list = []
    try:
        for reaction in message.reactions.all():
            try:
                user_name = reaction.user.get_full_name()
            except:
                user_name = reaction.user.utilisateur.email if reaction.user.utilisateur else "Utilisateur"
            
            reactions_list.append({
                'type': reaction.reaction_type,
                'emoji': reaction.get_reaction_type_display(),
                'user_id': reaction.user.id,
                'user_name': user_name
            })
    except:
        pass
    
    # Gestion du reply_to
    reply_to_data = None
    if message.reply_to:
        try:
            reply_sender_name = message.reply_to.sender.get_full_name()
        except:
            reply_sender_name = message.reply_to.sender.utilisateur.email if message.reply_to.sender.utilisateur else "Utilisateur"
        
        reply_to_data = {
            'id': str(message.reply_to.id),
            'content': (message.reply_to.content[:50] + '...' 
                       if message.reply_to.content and len(message.reply_to.content) > 50 
                       else message.reply_to.content),
            'sender_name': reply_sender_name,
            'message_type': message.reply_to.message_type
        }
    
    return {
        'id': str(message.id),
        'content': message.content,
        'sender_id': message.sender.id,
        'sender_name': sender_name,
        'sender_photo': message.sender.photo.url if message.sender.photo else None,
        'is_sent': message.sender == user_etudiant,
        'message_type': message.message_type,
        'created_at': message.created_at.isoformat(),
        'formatted_time': message.created_at.strftime('%H:%M'),
        'is_read': message.is_read,
        'is_edited': message.is_edited,
        'edited_at': message.edited_at.isoformat() if message.edited_at else None,
        'file_url': message.file.url if message.file else None,
        'file_name': os.path.basename(message.file.name) if message.file else None,
        'file_size': message.get_file_size_display() if message.file else None,
        'reply_to': reply_to_data,
        'reactions': reactions_list,
        'can_edit': message.can_be_edited(user_etudiant)
    }


# ========== VUES TEMPLATE ==========

@login_required
def conversations_list(request):
    """Vue pour afficher la liste des conversations avec support mobile"""
    user_etudiant = get_user_etudiant(request)
    
    # Paramètres de filtre
    filter_type = request.GET.get('filter', 'all')  # all, unread, archived
    search_query = request.GET.get('search', '').strip()
    
    # Base de la requête
    conversations_qs = Conversation.objects.get_user_conversations(
        user_etudiant, 
        include_archived=(filter_type == 'archived')
    )
    
    # Filtrer selon le type
    if filter_type == 'unread':
        conversations_qs = conversations_qs.annotate(
            unread_count=Count(
                'messages',
                filter=Q(
                    messages__receiver=user_etudiant,
                    messages__is_read=False,
                    messages__is_deleted_by_receiver=False
                )
            )
        ).filter(unread_count__gt=0)
    elif filter_type == 'archived':
        conversations_qs = conversations_qs.filter(
            Q(participant1=user_etudiant, archived_by_participant1=True) |
            Q(participant2=user_etudiant, archived_by_participant2=True)
        )
    
    # Recherche par nom d'utilisateur
    if search_query:
        conversations_qs = conversations_qs.filter(
            Q(participant1__utilisateur__first_name__icontains=search_query) |
            Q(participant1__utilisateur__last_name__icontains=search_query) |
            Q(participant1__utilisateur__username__icontains=search_query) |
            Q(participant2__utilisateur__first_name__icontains=search_query) |
            Q(participant2__utilisateur__last_name__icontains=search_query) |
            Q(participant2__utilisateur__username__icontains=search_query)
        )
    
    # Optimiser avec prefetch des derniers messages
    conversations_qs = conversations_qs.prefetch_related(
        Prefetch(
            'messages',
            queryset=Message.objects.filter(
                Q(is_deleted_by_sender=False) | Q(is_deleted_by_receiver=False)
            ).order_by('-created_at')[:1],
            to_attr='latest_messages'
        )
    )
    
    # Pagination
    paginator = Paginator(conversations_qs, 20)
    page_number = request.GET.get('page', 1)
    conversations_page = paginator.get_page(page_number)
    
    # Préparer les données pour chaque conversation
    conversation_data = []
    for conv in conversations_page:
        other_participant = conv.get_other_participant(user_etudiant)
        last_message = conv.latest_messages[0] if conv.latest_messages else None
        unread_count = conv.get_unread_count(user_etudiant)
        
        # Ajouter le statut en ligne (optionnel)
        try:
            other_participant.is_online = hasattr(other_participant.utilisateur, 'last_activity') and \
                                        (timezone.now() - other_participant.utilisateur.last_activity).seconds < 300
        except:
            other_participant.is_online = False
        
        conversation_data.append({
            'conversation': conv,
            'other_participant': other_participant,
            'last_message': last_message,
            'unread_count': unread_count,
            'is_archived': conv.is_archived_by(user_etudiant),
            'last_activity': conv.last_message_at or conv.created_at,
        })
    
    # Récupérer les amis disponibles pour créer de nouvelles conversations
    amis_disponibles = []
    if filter_type != 'archived':
        amis = Relation.objects.get_amis(user_etudiant)
        existing_participants = set()
        
        for conv_data in conversation_data:
            existing_participants.add(conv_data['other_participant'].id)
        
        for ami in amis:
            if ami.id not in existing_participants:
                amis_disponibles.append(ami)
    
    # Statistiques
    total_conversations = Conversation.objects.get_user_conversations(user_etudiant).count()
    total_unread = Message.objects.unread_for_user(user_etudiant).count()
    
    context = {
        'conversations': conversation_data,
        'conversations_page': conversations_page,
        'user_etudiant': user_etudiant,
        'amis_disponibles': amis_disponibles,
        'filter_type': filter_type,
        'search_query': search_query,
        'total_conversations': total_conversations,
        'total_unread': total_unread,
    }
    
    # Réponse AJAX pour les requêtes asynchrones
    if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
        conversations_json = []
        for conv_data in conversation_data:
            try:
                other_participant_name = conv_data['other_participant'].get_full_name()
            except:
                other_participant_name = conv_data['other_participant'].utilisateur.email
            
            last_message_data = None
            if conv_data['last_message']:
                last_message_data = {
                    'content': conv_data['last_message'].content,
                    'time': conv_data['last_message'].created_at.strftime('%H:%M'),
                    'type': conv_data['last_message'].message_type,
                    'sender_is_me': conv_data['last_message'].sender == user_etudiant,
                }
            
            conversations_json.append({
                'id': str(conv_data['conversation'].id),
                'other_participant': {
                    'id': conv_data['other_participant'].id,
                    'name': other_participant_name,
                    'photo': conv_data['other_participant'].photo.url if conv_data['other_participant'].photo else None,
                    'is_online': getattr(conv_data['other_participant'], 'is_online', False),
                },
                'last_message': last_message_data,
                'unread_count': conv_data['unread_count'],
                'is_archived': conv_data['is_archived'],
            })
        
        return JsonResponse({
            'success': True,
            'conversations': conversations_json,
            'has_next': conversations_page.has_next(),
            'has_previous': conversations_page.has_previous(),
            'total_count': total_conversations,
        })
    
    # Choisir le template selon l'appareil
    template_name = 'messagerie/conversation_list.html'
    
    return render(request, template_name, context)


@login_required
def chat_view(request, conversation_id):
    """Vue pour afficher une conversation spécifique avec support mobile"""
    user_etudiant = get_user_etudiant(request)
    
    try:
        conversation = get_object_or_404(Conversation, id=conversation_id)
    except ValueError:
        raise Http404("Conversation non trouvée")
    
    # Vérifier que l'utilisateur fait partie de la conversation
    if user_etudiant not in [conversation.participant1, conversation.participant2]:
        messages.error(request, "Vous n'avez pas accès à cette conversation.")
        return redirect('messagerie:conversations')
    
    # Vérifier que les utilisateurs peuvent encore communiquer
    other_participant = conversation.get_other_participant(user_etudiant)
    if not conversation.can_send_message(user_etudiant):
        messages.warning(request, "Vous ne pouvez plus envoyer de messages dans cette conversation.")
    
    # Récupérer les messages visibles
    messages_qs = Message.objects.get_conversation_messages(conversation, user_etudiant)
    
    # Pagination des messages (ordre chronologique inversé pour affichage)
    messages_per_page = int(request.GET.get('per_page', 50))
    paginator = Paginator(messages_qs.order_by('-created_at'), messages_per_page)
    page_number = request.GET.get('page', 1)
    messages_page = paginator.get_page(page_number)
    
    # Inverser l'ordre pour l'affichage (du plus ancien au plus récent)
    messages_list = list(reversed(messages_page.object_list))
    
    # Marquer les messages reçus comme lus (optimisé)
    conversation.mark_all_as_read(user_etudiant)
    
    # Récupérer ou créer les paramètres de conversation
    settings_obj, created = ConversationSettings.objects.get_or_create(
        conversation=conversation,
        user=user_etudiant
    )
    
    # Mettre à jour le dernier message vu
    if messages_list:
        settings_obj.last_seen_message = messages_list[-1]
        settings_obj.save(update_fields=['last_seen_message'])
    
    # Ajouter le statut en ligne
    try:
        other_participant.is_online = hasattr(other_participant.utilisateur, 'last_activity') and \
                                    (timezone.now() - other_participant.utilisateur.last_activity).seconds < 300
    except:
        other_participant.is_online = False
    
    context = {
        'conversation': conversation,
        'messages': messages_list,
        'messages_page': messages_page,
        'other_participant': other_participant,
        'user_etudiant': user_etudiant,
        'can_send_message': conversation.can_send_message(user_etudiant),
        'conversation_settings': settings_obj,
        'page_info': {
            'has_previous': messages_page.has_previous(),
            'has_next': messages_page.has_next(),
            'number': messages_page.number,
            'num_pages': paginator.num_pages,
        }
    }
    
    # Réponse AJAX pour le chargement de messages
    if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
        messages_json = [format_message_for_json(msg, user_etudiant) for msg in messages_list]
        return JsonResponse({
            'success': True,
            'messages': messages_json,
            'page_info': context['page_info']
        })
    
    # Choisir le template selon l'appareil
    template_name = 'messagerie/chat.html'
    
    return render(request, template_name, context)


@login_required
def start_conversation(request, ami_id):
    """Démarrer une nouvelle conversation avec un ami"""
    user_etudiant = get_user_etudiant(request)
    ami = get_object_or_404(Etudiant, id=ami_id)
    
    # Vérifier qu'ils sont amis et peuvent communiquer
    if not Relation.peuvent_communiquer(user_etudiant, ami):
        messages.error(request, "Vous devez être amis pour démarrer une conversation.")
        return redirect('messagerie:conversations')
    
    try:
        conversation, created = Conversation.objects.get_or_create_between_users(user_etudiant, ami)
        
        if created:
            messages.success(request, f"Nouvelle conversation créée avec {ami}.")
        
        # Désarchiver la conversation si elle était archivée
        if conversation.is_archived_by(user_etudiant):
            conversation.unarchive_for_user(user_etudiant)
            messages.info(request, "Conversation restaurée depuis les archives.")
        
        return redirect('messagerie:chat', conversation_id=conversation.id)
        
    except ValidationError as e:
        messages.error(request, f"Erreur: {str(e)}")
        return redirect('messagerie:conversations')


# ========== VUES AJAX ==========

@login_required
@require_http_methods(["POST"])
def send_message(request):
    """Envoyer un message via AJAX avec support des fichiers et validation renforcée"""
    user_etudiant = get_user_etudiant(request)

    try:
        # Gérer les données selon le type de requête
        if request.content_type and 'multipart/form-data' in request.content_type:
            # Données de formulaire avec fichier
            data = request.POST.dict()
            uploaded_file = request.FILES.get('file')
        else:
            # Données JSON
            data = json.loads(request.body)
            uploaded_file = None
            
        conversation_id = data.get('conversation_id')
        content = data.get('content', '').strip()
        message_type = data.get('message_type', 'text')
        reply_to_id = data.get('reply_to')

        # Validation de base
        if not content and not uploaded_file:
            return JsonResponse({'error': 'Le message ne peut pas être vide.'}, status=400)

        conversation = get_object_or_404(Conversation, id=conversation_id)

        # Vérifier les permissions
        if user_etudiant not in [conversation.participant1, conversation.participant2]:
            return JsonResponse({'error': 'Non autorisé.'}, status=403)
        
        if not conversation.can_send_message(user_etudiant):
            return JsonResponse({'error': 'Vous ne pouvez pas envoyer de messages dans cette conversation.'}, status=403)

        receiver = conversation.get_other_participant(user_etudiant)

        # Validation du fichier
        if uploaded_file:
            is_valid, error_msg = validate_uploaded_file(uploaded_file)
            if not is_valid:
                return JsonResponse({'error': error_msg}, status=400)

        # Gestion du message de réponse
        reply_to_msg = None
        if reply_to_id:
            try:
                reply_to_msg = Message.objects.get(
                    id=reply_to_id,
                    conversation=conversation
                )
            except Message.DoesNotExist:
                pass

        # Créer le message
        message_data = {
            'conversation': conversation,
            'sender': user_etudiant,
            'receiver': receiver,
            'content': content,
            'message_type': message_type,
            'reply_to': reply_to_msg
        }

        # Gérer les fichiers
        if uploaded_file:
            message_data['file'] = uploaded_file

        message = Message.objects.create(**message_data)

        # Préparer la réponse
        response_data = {
            'success': True,
            'message': format_message_for_json(message, user_etudiant)
        }

        return JsonResponse(response_data)

    except json.JSONDecodeError:
        return JsonResponse({'error': 'Données JSON invalides.'}, status=400)
    except Exception as e:
        return JsonResponse({'error': str(e)}, status=500)


@login_required
@require_http_methods(["POST"])
def edit_message(request, message_id):
    """Éditer un message existant"""
    try:
        data = json.loads(request.body)
        user_etudiant = get_user_etudiant(request)
        
        message = get_object_or_404(Message, id=message_id)
        new_content = data.get('content', '').strip()
        
        if not message.can_be_edited(user_etudiant):
            return JsonResponse({'error': 'Ce message ne peut plus être édité.'}, status=403)
        
        if not new_content:
            return JsonResponse({'error': 'Le contenu ne peut pas être vide.'}, status=400)
        
        if message.edit_content(new_content):
            return JsonResponse({
                'success': True,
                'message': format_message_for_json(message, user_etudiant)
            })
        else:
            return JsonResponse({'error': 'Impossible d\'éditer ce message.'}, status=400)
            
    except json.JSONDecodeError:
        return JsonResponse({'error': 'Données JSON invalides.'}, status=400)
    except Exception as e:
        return JsonResponse({'error': str(e)}, status=500)


@login_required
@require_http_methods(["POST"])
def mark_message_read(request, message_id):
    """Marquer un message comme lu"""
    try:
        user_etudiant = get_user_etudiant(request)
        message = get_object_or_404(Message, id=message_id, receiver=user_etudiant)
        message.mark_as_read()
        return JsonResponse({'success': True})
    except Message.DoesNotExist:
        return JsonResponse({'error': 'Message non trouvé.'}, status=404)
    except Exception as e:
        return JsonResponse({'error': str(e)}, status=500)


@login_required
@require_http_methods(["POST"])
def mark_conversation_read(request, conversation_id):
    """Marquer tous les messages d'une conversation comme lus"""
    try:
        user_etudiant = get_user_etudiant(request)
        conversation = get_object_or_404(Conversation, id=conversation_id)
        
        if user_etudiant not in [conversation.participant1, conversation.participant2]:
            return JsonResponse({'error': 'Non autorisé.'}, status=403)
        
        conversation.mark_all_as_read(user_etudiant)
        return JsonResponse({'success': True})
        
    except Exception as e:
        return JsonResponse({'error': str(e)}, status=500)


@login_required
@require_http_methods(["POST"])
def delete_message(request, message_id):
    """Supprimer un message"""
    try:
        user_etudiant = get_user_etudiant(request)
        message = get_object_or_404(Message, id=message_id)
        
        # Vérifier que l'utilisateur peut supprimer ce message
        if user_etudiant not in [message.sender, message.receiver]:
            return JsonResponse({'error': 'Non autorisé.'}, status=403)
        
        message.delete_for_user(user_etudiant)
        return JsonResponse({'success': True})
        
    except Message.DoesNotExist:
        return JsonResponse({'error': 'Message non trouvé.'}, status=404)
    except Exception as e:
        return JsonResponse({'error': str(e)}, status=500)


@login_required
@require_http_methods(["POST"])
def add_reaction(request, message_id):
    """Ajouter une réaction à un message"""
    try:
        data = json.loads(request.body)
        user_etudiant = get_user_etudiant(request)
        message = get_object_or_404(Message, id=message_id)
        reaction_type = data.get('reaction_type')
        
        # Vérifier que l'utilisateur fait partie de la conversation
        if user_etudiant not in [message.sender, message.receiver]:
            return JsonResponse({'error': 'Non autorisé.'}, status=403)
        
        # Vérifier que le type de réaction est valide
        valid_reactions = [choice[0] for choice in MessageReaction.REACTION_CHOICES]
        if reaction_type not in valid_reactions:
            return JsonResponse({'error': 'Type de réaction invalide.'}, status=400)
        
        # Ajouter ou modifier la réaction
        reaction, created = MessageReaction.objects.update_or_create(
            message=message,
            user=user_etudiant,
            defaults={'reaction_type': reaction_type}
        )
        
        return JsonResponse({
            'success': True,
            'reaction': {
                'type': reaction.reaction_type,
                'emoji': reaction.get_reaction_type_display(),
                'user_id': user_etudiant.id,
                'user_name': user_etudiant.utilisateur.get_full_name() or user_etudiant.utilisateur.username,
                'created': created
            }
        })
        
    except json.JSONDecodeError:
        return JsonResponse({'error': 'Données JSON invalides.'}, status=400)
    except Message.DoesNotExist:
        return JsonResponse({'error': 'Message non trouvé.'}, status=404)
    except Exception as e:
        return JsonResponse({'error': str(e)}, status=500)


@login_required
@require_http_methods(["POST"])
def remove_reaction(request, message_id):
    """Supprimer une réaction d'un message"""
    try:
        user_etudiant = get_user_etudiant(request)
        message = get_object_or_404(Message, id=message_id)
        
        deleted_count = MessageReaction.objects.filter(
            message=message,
            user=user_etudiant
        ).delete()[0]
        
        return JsonResponse({
            'success': True,
            'deleted': deleted_count > 0
        })
        
    except Message.DoesNotExist:
        return JsonResponse({'error': 'Message non trouvé.'}, status=404)
    except Exception as e:
        return JsonResponse({'error': str(e)}, status=500)


@login_required
@require_http_methods(["POST"])
def archive_conversation(request, conversation_id):
    """Archiver ou désarchiver une conversation"""
    try:
        data = json.loads(request.body) if request.body else {}
        user_etudiant = get_user_etudiant(request)
        conversation = get_object_or_404(Conversation, id=conversation_id)
        action = data.get('action', 'archive')  # 'archive' ou 'unarchive'
        
        # Vérifier que l'utilisateur fait partie de la conversation
        if user_etudiant not in [conversation.participant1, conversation.participant2]:
            return JsonResponse({'error': 'Non autorisé.'}, status=403)
        
        if action == 'archive':
            conversation.archive_for_user(user_etudiant)
            message = 'Conversation archivée.'
        elif action == 'unarchive':
            conversation.unarchive_for_user(user_etudiant)
            message = 'Conversation restaurée.'
        else:
            return JsonResponse({'error': 'Action invalide.'}, status=400)
        
        return JsonResponse({
            'success': True,
            'message': message,
            'is_archived': conversation.is_archived_by(user_etudiant)
        })
        
    except Conversation.DoesNotExist:
        return JsonResponse({'error': 'Conversation non trouvée.'}, status=404)
    except Exception as e:
        return JsonResponse({'error': str(e)}, status=500)


@login_required
def get_conversation_messages(request, conversation_id):
    """Récupérer les messages d'une conversation avec pagination"""
    try:
        user_etudiant = get_user_etudiant(request)
        conversation = get_object_or_404(Conversation, id=conversation_id)
        
        # Vérifier l'accès
        if user_etudiant not in [conversation.participant1, conversation.participant2]:
            return JsonResponse({'error': 'Non autorisé.'}, status=403)
        
        # Paramètres de pagination
        page = int(request.GET.get('page', 1))
        per_page = int(request.GET.get('per_page', 50))
        last_message_id = request.GET.get('last_message_id')
        
        # Récupérer les messages
        messages_qs = Message.objects.get_conversation_messages(conversation, user_etudiant)
        
        # Filtrer les nouveaux messages si un ID de référence est fourni
        if last_message_id:
            try:
                last_message = Message.objects.get(id=last_message_id)
                messages_qs = messages_qs.filter(created_at__gt=last_message.created_at)
            except Message.DoesNotExist:
                pass
        
        # Pagination
        paginator = Paginator(messages_qs.order_by('-created_at'), per_page)
        messages_page = paginator.get_page(page)
        
        # Formater les messages
        messages_data = [
            format_message_for_json(msg, user_etudiant) 
            for msg in reversed(messages_page.object_list)
        ]
        
        return JsonResponse({
            'success': True,
            'messages': messages_data,
            'page_info': {
                'has_previous': messages_page.has_previous(),
                'has_next': messages_page.has_next(),
                'number': messages_page.number,
                'num_pages': paginator.num_pages,
                'count': paginator.count
            }
        })
        
    except Exception as e:
        return JsonResponse({'error': str(e)}, status=500)


@login_required
def search_messages(request):
    """Rechercher dans les messages"""
    user_etudiant = get_user_etudiant(request)
    query = request.GET.get('q', '').strip()
    conversation_id = request.GET.get('conversation_id')
    
    if not query:
        return JsonResponse({'error': 'Requête de recherche vide.'}, status=400)
    
    # Base de la requête
    messages_qs = Message.objects.visible_for_user(user_etudiant).filter(
        content__icontains=query
    )
    
    # Filtrer par conversation si spécifié
    if conversation_id:
        messages_qs = messages_qs.filter(conversation_id=conversation_id)
    
    # Limiter les résultats
    messages_qs = messages_qs.select_related(
        'conversation',
        'sender__utilisateur',
        'receiver__utilisateur'
    ).order_by('-created_at')[:50]
    
    results = []
    for message in messages_qs:
        other_participant = message.conversation.get_other_participant(user_etudiant)
        results.append({
            'message_id': str(message.id),
            'conversation_id': str(message.conversation.id),
            'content': message.content,
            'sender_name': message.sender.utilisateur.get_full_name() or message.sender.utilisateur.username,
            'other_participant_name': other_participant.utilisateur.get_full_name() or other_participant.utilisateur.username,
            'created_at': message.created_at.isoformat(),
            'formatted_time': message.created_at.strftime('%d/%m/%Y %H:%M'),
        })
    
    return JsonResponse({
        'success': True,
        'results': results,
        'count': len(results)
    })


@login_required
@require_http_methods(["POST"])
def forward_message(request, message_id):
    """Transférer un message vers d'autres conversations"""
    try:
        data = json.loads(request.body)
        user_etudiant = get_user_etudiant(request)
        original_message = get_object_or_404(Message, id=message_id)
        conversation_ids = data.get('conversation_ids', [])
        
        # Vérifier que l'utilisateur peut voir le message original
        if not original_message.is_visible_for(user_etudiant):
            return JsonResponse({'error': 'Message non accessible.'}, status=403)
        
        if not conversation_ids:
            return JsonResponse({'error': 'Aucune conversation sélectionnée.'}, status=400)
        
        forwarded_count = 0
        errors = []
        
        for conv_id in conversation_ids:
            try:
                target_conversation = get_object_or_404(Conversation, id=conv_id)
                
                # Vérifier que l'utilisateur fait partie de la conversation cible
                if user_etudiant not in [target_conversation.participant1, target_conversation.participant2]:
                    errors.append(f"Accès refusé à la conversation {conv_id}")
                    continue
                
                # Vérifier que l'utilisateur peut envoyer des messages
                if not target_conversation.can_send_message(user_etudiant):
                    errors.append(f"Impossible d'envoyer dans la conversation {conv_id}")
                    continue
                
                receiver = target_conversation.get_other_participant(user_etudiant)
                
                # Créer le message transféré
                forwarded_content = f"Message transféré :\n{original_message.content}"
                
                Message.objects.create(
                    conversation=target_conversation,
                    sender=user_etudiant,
                    receiver=receiver,
                    content=forwarded_content,
                    message_type=original_message.message_type,
                    file=original_message.file
                )
                
                forwarded_count += 1
                
            except Exception as e:
                errors.append(f"Erreur pour conversation {conv_id}: {str(e)}")
        
        return JsonResponse({
            'success': True,
            'forwarded_count': forwarded_count,
            'errors': errors
        })
        
    except json.JSONDecodeError:
        return JsonResponse({'error': 'Données JSON invalides.'}, status=400)
    except Exception as e:
        return JsonResponse({'error': str(e)}, status=500)


@login_required
def conversation_settings(request, conversation_id):
    """Gérer les paramètres d'une conversation"""
    user_etudiant = get_user_etudiant(request)
    conversation = get_object_or_404(Conversation, id=conversation_id)
    
    # Vérifier l'accès
    if user_etudiant not in [conversation.participant1, conversation.participant2]:
        return JsonResponse({'error': 'Non autorisé.'}, status=403)
    
    settings_obj, created = ConversationSettings.objects.get_or_create(
        conversation=conversation,
        user=user_etudiant
    )
    
    if request.method == 'POST':
        try:
            data = json.loads(request.body)
            
            # Mettre à jour les paramètres
            for field in ['notifications_enabled', 'sound_enabled', 'auto_download_media']:
                if field in data:
                    setattr(settings_obj, field, data[field])
            
            if 'theme' in data and data['theme'] in ['default', 'dark', 'light']:
                settings_obj.theme = data['theme']
            
            settings_obj.save()
            
            return JsonResponse({
                'success': True,
                'settings': {
                    'notifications_enabled': settings_obj.notifications_enabled,
                    'sound_enabled': settings_obj.sound_enabled,
                    'auto_download_media': settings_obj.auto_download_media,
                    'theme': settings_obj.theme,
                }
            })
            
        except json.JSONDecodeError:
            return JsonResponse({'error': 'Données JSON invalides.'}, status=400)
        except Exception as e:
            return JsonResponse({'error': str(e)}, status=500)
    
    # GET request - retourner les paramètres actuels
    return JsonResponse({
        'success': True,
        'settings': {
            'notifications_enabled': settings_obj.notifications_enabled,
            'sound_enabled': settings_obj.sound_enabled,
            'auto_download_media': settings_obj.auto_download_media,
            'theme': settings_obj.theme,
        }
    })