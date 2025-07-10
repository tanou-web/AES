# relations/views.py
from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.db import IntegrityError, transaction
from django.http import HttpResponseForbidden, JsonResponse
from django.views.decorators.http import require_http_methods
from django.views.decorators.csrf import csrf_exempt
from django.core.paginator import Paginator
from django.db.models import Q, Count
import json

from .models import Relation, NotificationAmitie
from accounts.models import Etudiant


@login_required
def relations_page(request):
    """Page principale des relations avec filtres et pagination améliorés"""
    if request.user.is_staff or request.user.is_superuser:
        return redirect('admin:index')
    user_etudiant = get_object_or_404(Etudiant, utilisateur=request.user)

    # Utilisation des méthodes du manager
    demandes_recues = Relation.objects.get_demandes_recues(user_etudiant)
    demandes_envoyees = Relation.objects.get_demandes_envoyees(user_etudiant).filter(statut='envoyee')
    amis = Relation.objects.get_amis(user_etudiant)
    
    # Notifications non lues
    notifications_non_lues = NotificationAmitie.objects.filter(
        destinataire=user_etudiant,
        lu=False
    ).count()

    # Paramètres de filtre et pagination
    universite_filter = request.GET.get('universite')
    filiere_filter = request.GET.get('filiere')
    search_query = request.GET.get('search', '').strip()
    voir_plus = request.GET.get('voir_plus', False)
    
    # Limite des suggestions
    limit = 100 if voir_plus else 20
    
    # Récupérer les suggestions avec filtres
    suggestions = Relation.objects.get_suggestions(
        user_etudiant, 
        universite_filter=universite_filter,
        filiere_filter=filiere_filter,
        limit=limit
    )
    
    # Filtre de recherche par nom
    if search_query:
        suggestions = suggestions.filter(
            Q(utilisateur__first_name__icontains=search_query) |
            Q(utilisateur__last_name__icontains=search_query) |
            Q(utilisateur__username__icontains=search_query)
        )
    
    # Pagination des suggestions
    paginator = Paginator(suggestions, 20)
    page_number = request.GET.get('page', 1)
    suggestions_page = paginator.get_page(page_number)
    
    # Récupérer les options pour les filtres
    from referentiels.models import Universite, Filiere
    universites = Universite.objects.all()
    filieres = Filiere.objects.all()
    
    # Statistiques
    stats = {
        'total_amis': len(amis),
        'demandes_en_attente': demandes_recues.count(),
        'demandes_envoyees': demandes_envoyees.count(),
    }

    context = {
        'demandes_recues': demandes_recues,
        'demandes_envoyees': demandes_envoyees,
        'amis': amis,
        'suggestions': suggestions_page,
        'user_etudiant': user_etudiant,
        'universites': universites,
        'filieres': filieres,
        'notifications_non_lues': notifications_non_lues,
        'stats': stats,
        'search_query': search_query,
        'universite_filter': universite_filter,
        'filiere_filter': filiere_filter,
    }
    return render(request, 'relations/relations_page.html', context)


@login_required
@require_http_methods(["POST"])
def envoyer_demande(request, destinataire_id):
    """Envoie une demande d'amitié avec gestion des transactions"""
    expediteur = get_object_or_404(Etudiant, utilisateur=request.user)
    destinataire = get_object_or_404(Etudiant, pk=destinataire_id)
    
    # Vérifications de base
    if expediteur == destinataire:
        messages.error(request, "Vous ne pouvez pas vous envoyer une demande d'ami à vous-même.")
        return redirect('relations:page')

    try:
        with transaction.atomic():
            # Vérifier si une relation inverse existe
            relation_inverse = Relation.objects.filter(
                expediteur=destinataire, 
                destinataire=expediteur
            ).first()
            
            if relation_inverse:
                if relation_inverse.statut == 'envoyee':
                    # Accepter automatiquement la demande inverse
                    relation_inverse.accepter()
                    
                    # Créer les notifications
                    NotificationAmitie.objects.create(
                        destinataire=destinataire,
                        expediteur=expediteur,
                        relation=relation_inverse,
                        type_notification='demande_acceptee',
                        message=f"{expediteur.prenom} {expediteur.nom} a accepté votre demande d'amitié."
                    )
                    
                    messages.success(request, f"Vous êtes maintenant ami avec {destinataire}.")
                elif relation_inverse.statut == 'acceptee':
                    messages.info(request, f"Vous êtes déjà ami avec {destinataire}.")
                elif relation_inverse.statut == 'bloquee':
                    messages.error(request, "Impossible d'envoyer une demande à cet utilisateur.")
                else:
                    messages.warning(request, f"Une demande de {destinataire} a été refusée précédemment.")
                return redirect('relations:page')

            # Créer une nouvelle relation
            relation = Relation.objects.create(
                expediteur=expediteur, 
                destinataire=destinataire, 
                statut='envoyee'
            )
            
            # Créer la notification
            NotificationAmitie.objects.create(
                destinataire=destinataire,
                expediteur=expediteur,
                relation=relation,
                type_notification='demande_recue',
                message=f"{expediteur.prenom} {expediteur.nom} vous a envoyé une demande d'amitié."
            )
            
            messages.success(request, f"Demande d'ami envoyée à {destinataire}.")
            
    except IntegrityError:
        messages.info(request, "Cette demande a déjà été envoyée.")
    except Exception as e:
        messages.error(request, f"Erreur lors de l'envoi de la demande: {str(e)}")
    
    return redirect('relations:page')


@login_required
@require_http_methods(["POST"])
def repondre_demande(request, relation_id, action):
    """Répond à une demande d'amitié avec gestion améliorée"""
    user_etudiant = get_object_or_404(Etudiant, utilisateur=request.user)
    
    try:
        with transaction.atomic():
            if action == 'supprimer':
                # Pour supprimer/annuler, l'utilisateur doit être l'expéditeur
                relation = get_object_or_404(
                    Relation, 
                    id=relation_id, 
                    expediteur=user_etudiant
                )
                destinataire_nom = f"{relation.destinataire.prenom} {relation.destinataire.nom}"
                relation.delete()
                messages.info(request, f"Demande envoyée à {destinataire_nom} annulée.")
                
            else:
                # Pour accepter/refuser, l'utilisateur doit être le destinataire
                relation = get_object_or_404(
                    Relation, 
                    id=relation_id, 
                    destinataire=user_etudiant,
                    statut='envoyee'
                )

                if action == 'accepter':
                    relation.accepter()
                    
                    # Créer la notification pour l'expéditeur
                    NotificationAmitie.objects.create(
                        destinataire=relation.expediteur,
                        expediteur=user_etudiant,
                        relation=relation,
                        type_notification='demande_acceptee',
                        message=f"{user_etudiant.prenom} {user_etudiant.nom} a accepté votre demande d'amitié."
                    )
                    
                    messages.success(request, f"Vous êtes maintenant ami avec {relation.expediteur}.")
                    
                elif action == 'refuser':
                    relation.refuser()
                    
                    # Créer la notification pour l'expéditeur
                    NotificationAmitie.objects.create(
                        destinataire=relation.expediteur,
                        expediteur=user_etudiant,
                        relation=relation,
                        type_notification='demande_refusee',
                        message=f"{user_etudiant.prenom} {user_etudiant.nom} a refusé votre demande d'amitié."
                    )
                    
                    messages.info(request, f"Vous avez refusé la demande de {relation.expediteur}.")
                    
                elif action == 'bloquer':
                    relation.bloquer(user_etudiant)
                    messages.info(request, f"Vous avez bloqué {relation.expediteur}.")
                    
                else:
                    messages.error(request, "Action non reconnue.")
    
    except Relation.DoesNotExist:
        messages.error(request, "Relation non trouvée.")
    except Exception as e:
        messages.error(request, f"Erreur lors du traitement: {str(e)}")
    
    return redirect('relations:page')


@login_required
@require_http_methods(["POST"])
def bloquer_utilisateur(request, etudiant_id):
    """Bloque un utilisateur"""
    user_etudiant = get_object_or_404(Etudiant, utilisateur=request.user)
    etudiant_a_bloquer = get_object_or_404(Etudiant, id=etudiant_id)
    
    if user_etudiant == etudiant_a_bloquer:
        messages.error(request, "Vous ne pouvez pas vous bloquer vous-même.")
        return redirect('relations:page')
    
    try:
        with transaction.atomic():
            relation = Relation.objects.filter(
                Q(expediteur=user_etudiant, destinataire=etudiant_a_bloquer) |
                Q(expediteur=etudiant_a_bloquer, destinataire=user_etudiant)
            ).first()
            
            if relation:
                relation.bloquer(user_etudiant)
            else:
                # Créer une nouvelle relation bloquée
                Relation.objects.create(
                    expediteur=user_etudiant,
                    destinataire=etudiant_a_bloquer,
                    statut='bloquee',
                    bloque_par=user_etudiant
                )
            
            messages.success(request, f"Utilisateur {etudiant_a_bloquer} bloqué.")
            
    except Exception as e:
        messages.error(request, f"Erreur lors du blocage: {str(e)}")
    
    return redirect('relations:page')


@login_required
@require_http_methods(["POST"])
def debloquer_utilisateur(request, relation_id):
    """Débloque un utilisateur"""
    user_etudiant = get_object_or_404(Etudiant, utilisateur=request.user)
    
    try:
        relation = get_object_or_404(
            Relation,
            id=relation_id,
            statut='bloquee',
            bloque_par=user_etudiant
        )
        
        relation.debloquer()
        autre_etudiant = (
            relation.destinataire if relation.expediteur == user_etudiant 
            else relation.expediteur
        )
        messages.success(request, f"Utilisateur {autre_etudiant} débloqué.")
        
    except Exception as e:
        messages.error(request, f"Erreur lors du déblocage: {str(e)}")
    
    return redirect('relations:page')


@login_required
def notifications_amitie(request):
    """Affiche les notifications d'amitié"""
    user_etudiant = get_object_or_404(Etudiant, utilisateur=request.user)
    
    notifications = NotificationAmitie.objects.filter(
        destinataire=user_etudiant
    ).select_related('expediteur__utilisateur', 'relation').order_by('-date_creation')
    
    # Pagination
    paginator = Paginator(notifications, 20)
    page_number = request.GET.get('page', 1)
    notifications_page = paginator.get_page(page_number)
    
    # Marquer comme lues
    NotificationAmitie.objects.filter(
        destinataire=user_etudiant,
        lu=False
    ).update(lu=True)
    
    context = {
        'notifications': notifications_page,
        'user_etudiant': user_etudiant,
    }
    return render(request, 'relations/notifications.html', context)


# ========== VUES AJAX ==========

@login_required
@require_http_methods(["POST"])
def ajax_envoyer_demande(request):
    """Version AJAX pour envoyer une demande d'amitié"""
    try:
        data = json.loads(request.body)
        destinataire_id = data.get('destinataire_id')
        
        expediteur = get_object_or_404(Etudiant, utilisateur=request.user)
        destinataire = get_object_or_404(Etudiant, pk=destinataire_id)
        
        if expediteur == destinataire:
            return JsonResponse({
                'success': False,
                'message': "Vous ne pouvez pas vous envoyer une demande à vous-même."
            })

        with transaction.atomic():
            # Vérifier les relations existantes
            relation_existante = Relation.objects.filter(
                Q(expediteur=expediteur, destinataire=destinataire) |
                Q(expediteur=destinataire, destinataire=expediteur)
            ).first()
            
            if relation_existante:
                if relation_existante.statut == 'acceptee':
                    return JsonResponse({
                        'success': False,
                        'message': "Vous êtes déjà amis."
                    })
                elif relation_existante.statut == 'envoyee':
                    if relation_existante.expediteur == destinataire:
                        # Accepter automatiquement
                        relation_existante.accepter()
                        return JsonResponse({
                            'success': True,
                            'message': f"Vous êtes maintenant ami avec {destinataire}.",
                            'action': 'accepted'
                        })
                    else:
                        return JsonResponse({
                            'success': False,
                            'message': "Demande déjà envoyée."
                        })
                elif relation_existante.statut == 'bloquee':
                    return JsonResponse({
                        'success': False,
                        'message': "Impossible d'envoyer une demande à cet utilisateur."
                    })
            
            # Créer nouvelle relation
            relation = Relation.objects.create(
                expediteur=expediteur,
                destinataire=destinataire,
                statut='envoyee'
            )
            
            # Créer notification
            NotificationAmitie.objects.create(
                destinataire=destinataire,
                expediteur=expediteur,
                relation=relation,
                type_notification='demande_recue',
                message=f"{expediteur.prenom} {expediteur.nom} vous a envoyé une demande d'amitié."
            )
            
            return JsonResponse({
                'success': True,
                'message': f"Demande d'ami envoyée à {destinataire}.",
                'action': 'sent'
            })
            
    except json.JSONDecodeError:
        return JsonResponse({
            'success': False,
            'message': "Données JSON invalides."
        })
    except Exception as e:
        return JsonResponse({
            'success': False,
            'message': f"Erreur: {str(e)}"
        })


@login_required
def ajax_suggestions(request):
    """Récupère les suggestions d'amis via AJAX"""
    try:
        user_etudiant = get_object_or_404(Etudiant, utilisateur=request.user)
        
        # Paramètres de la requête
        universite_filter = request.GET.get('universite')
        filiere_filter = request.GET.get('filiere')
        search_query = request.GET.get('search', '').strip()
        page = int(request.GET.get('page', 1))
        limit = int(request.GET.get('limit', 20))
        
        # Récupérer les suggestions
        suggestions = Relation.objects.get_suggestions(
            user_etudiant,
            universite_filter=universite_filter,
            filiere_filter=filiere_filter,
            limit=limit * page
        )
        
        # Filtre de recherche
        if search_query:
            suggestions = suggestions.filter(
                Q(utilisateur__first_name__icontains=search_query) |
                Q(utilisateur__last_name__icontains=search_query) |
                Q(utilisateur__username__icontains=search_query)
            )
        
        # Pagination manuelle
        start = (page - 1) * limit
        end = start + limit
        suggestions_page = suggestions[start:end]
        
        # Formater les données
        suggestions_data = []
        for etudiant in suggestions_page:
            suggestions_data.append({
                'id': etudiant.id,
                'nom': f"{etudiant.prenom} {etudiant.nom}",
                'username': etudiant.utilisateur.username,
                'universite': etudiant.universite.nom if etudiant.universite else '',
                'filiere': etudiant.filiere.nom if etudiant.filiere else '',
                'photo_url': etudiant.photo.url if etudiant.photo else None,
            })
        
        return JsonResponse({
            'success': True,
            'suggestions': suggestions_data,
            'has_more': len(suggestions) > end
        })
        
    except Exception as e:
        return JsonResponse({
            'success': False,
            'message': f"Erreur: {str(e)}"
        })


@login_required
def statistiques_relations(request):
    """Affiche les statistiques des relations de l'utilisateur"""
    user_etudiant = get_object_or_404(Etudiant, utilisateur=request.user)
    
    # Statistiques de base
    stats = {
        'total_amis': Relation.objects.filter(
            Q(expediteur=user_etudiant) | Q(destinataire=user_etudiant),
            statut='acceptee'
        ).count(),
        'demandes_recues': Relation.objects.filter(
            destinataire=user_etudiant,
            statut='envoyee'
        ).count(),
        'demandes_envoyees': Relation.objects.filter(
            expediteur=user_etudiant,
            statut='envoyee'
        ).count(),
        'demandes_refusees': Relation.objects.filter(
            Q(expediteur=user_etudiant) | Q(destinataire=user_etudiant),
            statut='refusee'
        ).count(),
        'utilisateurs_bloques': Relation.objects.filter(
            bloque_par=user_etudiant,
            statut='bloquee'
        ).count(),
    }
    
    # Répartition par université
    amis = Relation.objects.get_amis(user_etudiant)
    stats_universite = {}
    stats_filiere = {}
    
    for ami in amis:
        if ami.universite:
            uni_nom = ami.universite.nom
            stats_universite[uni_nom] = stats_universite.get(uni_nom, 0) + 1
        
        if ami.filiere:
            fil_nom = ami.filiere.nom
            stats_filiere[fil_nom] = stats_filiere.get(fil_nom, 0) + 1
    
    context = {
        'stats': stats,
        'stats_universite': stats_universite,
        'stats_filiere': stats_filiere,
        'user_etudiant': user_etudiant,
    }
    
    if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
        return JsonResponse(context)
    
    return render(request, 'relations/statistiques.html', context)