from django.urls import path, include
from rest_framework.routers import DefaultRouter
from .views import VisitedCountryViewSet

router = DefaultRouter()
router.register(r'visited-countries', VisitedCountryViewSet, basename='visited-countries')

urlpatterns = [
    path('', include(router.urls)),
]