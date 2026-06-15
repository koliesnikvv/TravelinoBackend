from django.urls import path
from .views import (
    CityListView,
    CityDetailView,
    RecommendedCitiesView,
    ActivityListView,
    ActivityDetailView,
    TransportOptionListView,
    TransportOptionDetailView,
    AccommodationOptionListView,
    AccommodationOptionDetailView,
    CityInsightsView,
)

app_name = 'catalog'

urlpatterns = [
    path('cities/', CityListView.as_view(), name='city-list'),
    path('cities/recommended/', RecommendedCitiesView.as_view(), name='city-recommended'),
    path('cities/<uuid:pk>/', CityDetailView.as_view(), name='city-detail'),
    path('cities/<uuid:pk>/insights/', CityInsightsView.as_view(), name='city-insights'),

    path('activities/', ActivityListView.as_view(), name='activity-list'),
    path('activities/<str:pk>/', ActivityDetailView.as_view(), name='activity-detail'),

    path('transport/', TransportOptionListView.as_view(), name='transport-list'),
    path('transport/<uuid:pk>/', TransportOptionDetailView.as_view(), name='transport-detail'),

    path('accommodations/', AccommodationOptionListView.as_view(), name='accommodation-list'),
    path('accommodations/<uuid:pk>/', AccommodationOptionDetailView.as_view(), name='accommodation-detail'),
]