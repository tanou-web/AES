from django.urls import path, include
from rest_framework.routers import DefaultRouter
from .views import UniversiteViewSet, FiliereViewSet
from django.db import router

router = DefaultRouter()
router.register(r'universites', UniversiteViewSet)
router.register(r'filiere', FiliereViewSet)

urlpatterns = [
    path('',include(router.urls)),
  ]
