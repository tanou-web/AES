from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth import login, logout, authenticate
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.core.exceptions import ValidationError
from django.http import JsonResponse
from django.db.models import Q, Count
from django.views.decorators.http import require_http_methods
from django.contrib.auth.forms import PasswordChangeForm
from django.contrib.auth import update_session_auth_hash

from .models import Etudiant, CustomUser
from referentiels.models import Universite, Filiere
from .forms import UserRegistrationForm, ModernLoginForm, EtudiantRegistrationForm, ProfileUpdateForm
from relations.models import Relation

def home_view(request):
    """Page d'accueil avec statistiques"""
    if request.user.is_authenticated:
        return redirect('accounts:profile')
    
    # Statistiques pour la page d'accueil
    stats = {
        'total_etudiants': Etudiant.objects.count(),
        'total_universites': Universite.objects.count(),
        'total_relations': Relation.objects.filter(statut='acceptee').count() // 2,  # Diviser par 2 car chaque relation est comptée deux fois
    }
    
    return render(request, 'accounts/home.html', {'stats': stats})

def register_view(request):
    """Inscription en deux étapes avec validation améliorée"""
    step = request.session.get('register_step', 1)
    user_data = request.session.get('user_data', {})
    
    if request.method == 'POST':
        if step == 1:
            # Étape 1: Informations de compte
            form = UserRegistrationForm(request.POST)
            if form.is_valid():
                user_data = {
                    'email': form.cleaned_data['email'],
                    'password': form.cleaned_data['password'],
                }
                request.session['user_data'] = user_data
                request.session['register_step'] = 2
                messages.success(request, "Étape 1 terminée ! Complétez votre profil.")
                return redirect('accounts:register')
            else:
                messages.error(request, "Veuillez corriger les erreurs ci-dessous.")
        
        else:
            # Étape 2: Profil étudiant
            etudiant_form = EtudiantRegistrationForm(request.POST, request.FILES)
            
            if etudiant_form.is_valid():
                try:
                    # Créer l'utilisateur
                    user = CustomUser.objects.create_user(
                        email=user_data['email'],
                        password=user_data['password'],
                        role='etudiant'
                    )
                    
                    # Créer le profil étudiant
                    etudiant = etudiant_form.save(commit=False)
                    etudiant.utilisateur = user
                    etudiant.save()
                    
                    # Nettoyer la session
                    del request.session['user_data']
                    del request.session['register_step']
                    
                    # Connexion automatique
                    login(request, user)
                    
                    messages.success(request, f"Bienvenue {etudiant.prenom} ! Votre compte a été créé avec succès.")
                    return redirect('accounts:profile')
                    
                except ValidationError as e:
                    messages.error(request, str(e))
                    if 'user' in locals():
                        user.delete()
                except Exception as e:
                    messages.error(request, "Une erreur est survenue lors de l'inscription.")
                    if 'user' in locals():
                        user.delete()
            else:
                messages.error(request, "Veuillez corriger les erreurs dans le formulaire.")
    
    # Afficher le formulaire approprié
    if step == 1:
        form = UserRegistrationForm()
        template = 'accounts/register_step1.html'
        context = {'form': form}
    else:
        form = EtudiantRegistrationForm()
        template = 'accounts/register_step2.html'
        context = {'form': form, 'user_email': user_data.get('email', '')}
    
    return render(request, template, context)

@require_http_methods(["GET"])
def get_filieres(request):
    """API pour récupérer les filières par université"""
    universite_id = request.GET.get('universite')
    if universite_id:
        try:
            filieres = Filiere.objects.filter(
                universite_id=universite_id
            ).values('id', 'nom').order_by('nom')
            return JsonResponse(list(filieres), safe=False)
        except Exception as e:
            return JsonResponse({'error': 'Erreur lors du chargement des filières'}, status=400)
    return JsonResponse([], safe=False)

def login_view(request):
    """Connexion avec design moderne"""
    if request.user.is_authenticated:
        return redirect('accounts:profile')
    
    if request.method == 'POST':
        form = ModernLoginForm(request.POST)
        if form.is_valid():
            user = form.cleaned_data['user']
            login(request, user)
            
            # Gestion du "Se souvenir de moi"
            if not form.cleaned_data.get('remember_me'):
                request.session.set_expiry(0)  # Session expire à la fermeture du navigateur
            
            messages.success(request, f"Bon retour, {user.email}!")
            
            # Redirection intelligente
            next_url = request.GET.get('next')
            if next_url and next_url.startswith('/'):
                return redirect(next_url)
            return redirect('accounts:profile')
        else:
            messages.error(request, "Vérifiez vos informations de connexion.")
    else:
        form = ModernLoginForm()
    
    return render(request, 'accounts/login.html', {'form': form})

@login_required
def logout_view(request):
    """Déconnexion sécurisée"""
    user_name = request.user.email
    logout(request)
    messages.info(request, f"À bientôt, {user_name}!")
    return redirect('accounts:home')

@login_required
def profile_view(request):
    """Profil utilisateur avec statistiques"""
    user = request.user
    
    if user.role != 'etudiant':
        messages.error(request, "Accès réservé aux étudiants.")
        return redirect('accounts:home')
    
    try:
        etudiant = user.etudiant
    except Etudiant.DoesNotExist:
        messages.error(request, "Profil étudiant introuvable.")
        return redirect('accounts:home')
    
    # Statistiques du profil
    relations_stats = {
        'amis': Relation.objects.filter(
            (Q(expediteur=etudiant) | Q(destinataire=etudiant)),
            statut='acceptee'
        ).count(),
        'demandes_recues': Relation.objects.filter(
            destinataire=etudiant,
            statut='envoyee'
        ).count(),
        'demandes_envoyees': Relation.objects.filter(
            expediteur=etudiant,
            statut='envoyee'
        ).count()
    }
    
    # Amis récents
    relations_amis = Relation.objects.filter(
        (Q(expediteur=etudiant) | Q(destinataire=etudiant)),
        statut='acceptee'
    ).select_related('expediteur', 'destinataire').order_by('-date_modification')[:6]
    
    amis_recents = []
    for relation in relations_amis:
        ami = relation.destinataire if relation.expediteur == etudiant else relation.expediteur
        amis_recents.append(ami)
    
    context = {
        'etudiant': etudiant,
        'relations_stats': relations_stats,
        'amis_recents': amis_recents
    }
    
    return render(request, 'accounts/profile.html', context)

@login_required
def edit_profile_view(request):
    """Modification du profil"""
    if request.user.role != 'etudiant':
        messages.error(request, "Accès réservé aux étudiants.")
        return redirect('accounts:home')
    
    etudiant = get_object_or_404(Etudiant, utilisateur=request.user)
    
    if request.method == 'POST':
        form = ProfileUpdateForm(request.POST, request.FILES, instance=etudiant)
        if form.is_valid():
            form.save()
            messages.success(request, "Profil mis à jour avec succès !")
            return redirect('accounts:profile')
        else:
            messages.error(request, "Veuillez corriger les erreurs ci-dessous.")
    else:
        form = ProfileUpdateForm(instance=etudiant)
    
    return render(request, 'accounts/edit_profile.html', {'form': form, 'etudiant': etudiant})

@login_required
def change_password_view(request):
    """Changement de mot de passe"""
    if request.method == 'POST':
        form = PasswordChangeForm(request.user, request.POST)
        if form.is_valid():
            user = form.save()
            update_session_auth_hash(request, user)  # Garde l'utilisateur connecté
            messages.success(request, "Mot de passe modifié avec succès !")
            return redirect('accounts:profile')
        else:
            messages.error(request, "Veuillez corriger les erreurs ci-dessous.")
    else:
        form = PasswordChangeForm(request.user)
    
    return render(request, 'accounts/change_password.html', {'form': form})

@login_required
def view_profile(request, etudiant_id):
    """Vue du profil d'un autre étudiant"""
    etudiant = get_object_or_404(Etudiant, id=etudiant_id)
    current_user_etudiant = get_object_or_404(Etudiant, utilisateur=request.user)

    # Vérifier si c'est son propre profil
    is_own_profile = etudiant == current_user_etudiant

    # Vérifier si le profil est privé et si l'utilisateur est autorisé
    can_view_full_profile = True
    if etudiant.profil_prive and not is_own_profile:
        is_friend = Relation.objects.filter(
            (Q(expediteur=current_user_etudiant, destinataire=etudiant) | 
             Q(expediteur=etudiant, destinataire=current_user_etudiant)), 
            statut='acceptee'
        ).exists()

        if not is_friend:
            can_view_full_profile = False

    # Informations sur la relation
    relation_status = None
    relation_obj = None
    if not is_own_profile:
        relation_obj = Relation.objects.filter(
            (Q(expediteur=current_user_etudiant, destinataire=etudiant) | 
             Q(expediteur=etudiant, destinataire=current_user_etudiant))
        ).first()
        
        if relation_obj:
            if relation_obj.statut == 'acceptee':
                relation_status = 'friend'
            elif relation_obj.statut == 'envoyee':
                if relation_obj.expediteur == current_user_etudiant:
                    relation_status = 'request_sent'
                else:
                    relation_status = 'request_received'
            elif relation_obj.statut == 'bloquee':
                relation_status = 'blocked'
        else:
            relation_status = 'none'
    
    # Compter les amis
    nombre_amis = Relation.objects.filter(
        (Q(expediteur=etudiant) | Q(destinataire=etudiant)),
        statut='acceptee'
    ).count()
    
    # Amis en commun (si autorisé)
    amis_communs = []
    if can_view_full_profile and not is_own_profile:
        amis_etudiant = Relation.objects.filter(
            (Q(expediteur=etudiant) | Q(destinataire=etudiant)),
            statut='acceptee'
        )
        amis_current_user = Relation.objects.filter(
            (Q(expediteur=current_user_etudiant) | Q(destinataire=current_user_etudiant)),
            statut='acceptee'
        )
        
        # Logique pour trouver les amis communs
        # (implémentation simplifiée)
        
    context = {
        'etudiant': etudiant,
        'is_own_profile': is_own_profile,
        'can_view_full_profile': can_view_full_profile,
        'relation_status': relation_status,
        'relation_obj': relation_obj,
        'nombre_amis': nombre_amis,
        'amis_communs': amis_communs,
    }
    
    return render(request, 'accounts/view_profile.html', context)

@login_required
def search_users(request):
    """Recherche d'utilisateurs"""
    query = request.GET.get('q', '').strip()
    if len(query) < 2:
        return JsonResponse({'results': []})
    
    current_user_etudiant = get_object_or_404(Etudiant, utilisateur=request.user)
    
    # Recherche dans les étudiants
    etudiants = Etudiant.objects.filter(
        Q(nom__icontains=query) | 
        Q(prenom__icontains=query) |
        Q(utilisateur__email__icontains=query)
    ).exclude(
        id=current_user_etudiant.id
    ).select_related('utilisateur', 'universite', 'filiere')[:10]
    
    results = []
    for etudiant in etudiants:
        results.append({
            'id': etudiant.id,
            'name': etudiant.get_full_name(),
            'email': etudiant.utilisateur.email,
            'university': str(etudiant.universite) if etudiant.universite else '',
            'photo_url': etudiant.photo.url if etudiant.photo else None,
            'profile_url': f"/accounts/profile/{etudiant.id}/"
        })
    
    return JsonResponse({'results': results})

import json
from django.http import HttpResponse, JsonResponse
from django.views.decorators.http import require_POST
from django.contrib.auth.decorators import login_required
from django.db.models import Q

@login_required
@require_POST  
def toggle_privacy(request):
    """API pour changer la confidentialité du profil"""
    try:
        data = json.loads(request.body)
        profil_prive = data.get('profil_prive', False)
        
        etudiant = request.user.etudiant
        etudiant.profil_prive = profil_prive
        etudiant.save()
        
        return JsonResponse({
            'success': True,
            'message': 'Paramètres de confidentialité mis à jour'
        })
    except Exception as e:
        return JsonResponse({
            'success': False,
            'error': str(e)
        }, status=400)

@login_required
def download_profile_data(request):
    """Vue pour télécharger les données utilisateur"""
    try:
        etudiant = request.user.etudiant
        
        # Collecter les données
        user_data = {
            'profil': {
                'nom': etudiant.nom,
                'prenom': etudiant.prenom,
                'email': etudiant.utilisateur.email,
                'telephone': etudiant.telephone,
                'ville': etudiant.ville,
                'date_naissance': str(etudiant.date_naissance) if etudiant.date_naissance else None,
                'genre': etudiant.genre,
                'universite': str(etudiant.universite) if etudiant.universite else None,
                'filiere': str(etudiant.filiere) if etudiant.filiere else None,
                'annee_universitaire': etudiant.annee_universitaire,
                'situation': etudiant.situation,
                'date_creation': str(etudiant.utilisateur.date_joined),
            },
            'relations': [],
            'statistiques': {
                'total_amis': 0,
                'demandes_envoyees': 0,
                'demandes_recues': 0,
            }
        }
        
        # Ajouter les relations si le modèle existe
        try:
            from relations.models import Relation
            relations = Relation.objects.filter(
                Q(expediteur=etudiant) | Q(destinataire=etudiant)
            ).select_related('expediteur', 'destinataire')
            
            for relation in relations:
                ami = relation.destinataire if relation.expediteur == etudiant else relation.expediteur
                user_data['relations'].append({
                    'ami': f"{ami.prenom} {ami.nom}",
                    'statut': relation.statut,
                    'date_creation': str(relation.date_creation),
                    'date_modification': str(relation.date_modification),
                })
            
            # Calculer les statistiques
            user_data['statistiques']['total_amis'] = relations.filter(statut='acceptee').count()
            user_data['statistiques']['demandes_envoyees'] = relations.filter(
                expediteur=etudiant, statut='envoyee'
            ).count()
            user_data['statistiques']['demandes_recues'] = relations.filter(
                destinataire=etudiant, statut='envoyee'
            ).count()
        except ImportError:
            # Si le modèle Relation n'existe pas encore
            pass
        
        # Créer la réponse JSON
        response = HttpResponse(
            json.dumps(user_data, indent=2, ensure_ascii=False),
            content_type='application/json; charset=utf-8'
        )
        response['Content-Disposition'] = f'attachment; filename="mes_donnees_{etudiant.prenom}_{etudiant.nom}.json"'
        
        return response
        
    except Exception as e:
        messages.error(request, f'Erreur lors de l\'export: {str(e)}')
        return redirect('accounts:profile')

@login_required
@require_POST
def export_data(request):
    """API pour exporter les données (via AJAX)"""
    return download_profile_data(request)