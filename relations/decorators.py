from functools import wraps
from django.shortcuts import get_object_or_404, redirect
from django.contrib import messages
from django.http import JsonResponse
from accounts.models import Etudiant
from .models import Relation


def require_friendship(view_func):
    """
    Décorateur qui vérifie que deux utilisateurs sont amis
    """
    @wraps(view_func)
    def wrapper(request, ami_id, *args, **kwargs):
        user_etudiant = get_object_or_404(Etudiant, utilisateur=request.user)
        ami = get_object_or_404(Etudiant, id=ami_id)
        
        if not Relation.sont_amis(user_etudiant, ami):
            if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
                return JsonResponse({
                    'error': 'Vous devez être amis pour effectuer cette action.'
                }, status=403)
            else:
                messages.error(request, 'Vous devez être amis pour effectuer cette action.')
                return redirect('relations:page')
        
        return view_func(request, ami_id, *args, **kwargs)
    return wrapper


def can_communicate(view_func):
    """
    Décorateur qui vérifie que deux utilisateurs peuvent communiquer
    """
    @wraps(view_func)
    def wrapper(request, ami_id, *args, **kwargs):
        user_etudiant = get_object_or_404(Etudiant, utilisateur=request.user)
        ami = get_object_or_404(Etudiant, id=ami_id)
        
        if not Relation.peuvent_communiquer(user_etudiant, ami):
            if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
                return JsonResponse({
                    'error': 'Vous ne pouvez pas communiquer avec cet utilisateur.'
                }, status=403)
            else:
                messages.error(request, 'Vous ne pouvez pas communiquer avec cet utilisateur.')
                return redirect('relations:page')
        
        return view_func(request, ami_id, *args, **kwargs)
    return wrapper
