from django.db.models import Q, Count
from django.core.cache import cache
from .models import Relation, NotificationAmitie


def get_relations_stats(etudiant):
    """
    Récupère les statistiques des relations pour un étudiant avec mise en cache
    """
    cache_key = f'relations_stats_{etudiant.id}'
    stats = cache.get(cache_key)
    
    if stats is None:
        stats = {
            'total_amis': Relation.objects.filter(
                Q(expediteur=etudiant) | Q(destinataire=etudiant),
                statut='acceptee'
            ).count(),
            'demandes_recues': Relation.objects.filter(
                destinataire=etudiant,
                statut='envoyee'
            ).count(),
            'demandes_envoyees': Relation.objects.filter(
                expediteur=etudiant,
                statut='envoyee'
            ).count(),
            'notifications_non_lues': NotificationAmitie.objects.filter(
                destinataire=etudiant,
                lu=False
            ).count(),
        }
        
        # Cache pour 5 minutes
        cache.set(cache_key, stats, 300)
    
    return stats


def invalidate_relations_cache(etudiant):
    """
    Invalide le cache des relations pour un étudiant
    """
    cache.delete(f'relations_stats_{etudiant.id}')


def get_mutual_friends(etudiant1, etudiant2):
    """
    Récupère les amis en commun entre deux étudiants
    """
    amis_etudiant1 = set(Relation.objects.get_amis(etudiant1))
    amis_etudiant2 = set(Relation.objects.get_amis(etudiant2))
    
    return list(amis_etudiant1.intersection(amis_etudiant2))


def suggest_friends_advanced(etudiant, limit=10):
    """
    Suggestions d'amis avancées basées sur les amis en commun et les intérêts
    """
    # Récupérer les amis actuels
    amis_actuels = Relation.objects.get_amis(etudiant)
    amis_ids = [ami.id for ami in amis_actuels]
    amis_ids.append(etudiant.id)  # Exclure l'utilisateur lui-même
    
    # Récupérer les relations existantes
    relations_existantes = Relation.objects.filter(
        Q(expediteur=etudiant) | Q(destinataire=etudiant)
    ).values_list('expediteur_id', 'destinataire_id')
    
    exclus_ids = set()
    for exp_id, dest_id in relations_existantes:
        exclus_ids.add(exp_id)
        exclus_ids.add(dest_id)
    
    # Suggestions basées sur les amis d'amis
    from accounts.models import Etudiant
    suggestions = Etudiant.objects.exclude(
        id__in=exclus_ids
    ).filter(
        # Amis d'amis
        Q(relations_envoyees__destinataire__in=amis_actuels, relations_envoyees__statut='acceptee') |
        Q(relations_recues__expediteur__in=amis_actuels, relations_recues__statut='acceptee')
    ).annotate(
        # Compter les amis en commun
        amis_communs=Count('id')
    ).filter(
        # Même université ou filière
        Q(universite=etudiant.universite) | Q(filiere=etudiant.filiere)
    ).distinct().order_by('-amis_communs')[:limit]
    
    return suggestions