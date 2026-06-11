from django.urls import path, include
from rest_framework.routers import DefaultRouter

from . import views
from .views import (
    TripViewSet,
    TransportBookingViewSet,
    AccommodationBookingViewSet,
    TripActivityViewSet,
    TripParticipantViewSet,

)

router = DefaultRouter()
router.register(r'', TripViewSet, basename='trip')

# {trip_pk} is passed into self.kwargs['trip_pk'] in each nested ViewSet.
#
# GET     /api/trips/{trip_pk}/transport/              -> TransportBookingViewSet.list
# POST    /api/trips/{trip_pk}/transport/              -> TransportBookingViewSet.create
# GET     /api/trips/{trip_pk}/transport/{pk}/         -> TransportBookingViewSet.retrieve
# PATCH   /api/trips/{trip_pk}/transport/{pk}/         -> TransportBookingViewSet.partial_update
# DELETE  /api/trips/{trip_pk}/transport/{pk}/         -> TransportBookingViewSet.destroy
#
# Same pattern for accommodation, activities, participants.

transport_list = TransportBookingViewSet.as_view({'get': 'list', 'post': 'create'})
transport_detail = TransportBookingViewSet.as_view({'get': 'retrieve', 'patch': 'partial_update', 'put': 'update', 'delete': 'destroy'})

accommodation_list = AccommodationBookingViewSet.as_view({'get': 'list', 'post': 'create'})
accommodation_detail = AccommodationBookingViewSet.as_view({'get': 'retrieve', 'patch': 'partial_update', 'put': 'update', 'delete': 'destroy'})

activities_list = TripActivityViewSet.as_view({'get': 'list', 'post': 'create'})
activities_detail = TripActivityViewSet.as_view({'get': 'retrieve', 'patch': 'partial_update', 'put': 'update', 'delete': 'destroy'})

participants_list = TripParticipantViewSet.as_view({'get': 'list', 'post': 'create'})
participants_detail = TripParticipantViewSet.as_view({'get': 'retrieve', 'delete': 'destroy'})
participants_accept = TripParticipantViewSet.as_view({'post': 'accept_invite'})

urlpatterns = [
    path('', include(router.urls)),

    path('<uuid:trip_pk>/transport/', transport_list, name='trip-transport-list'),
    path('<uuid:trip_pk>/transport/<uuid:pk>/', transport_detail, name='trip-transport-detail'),

    path('<uuid:trip_pk>/accommodation/', accommodation_list, name='trip-accommodation-list'),
    path('<uuid:trip_pk>/accommodation/<uuid:pk>/', accommodation_detail, name='trip-accommodation-detail'),

    path('<uuid:trip_pk>/activities/', activities_list, name='trip-activities-list'),
    path('<uuid:trip_pk>/activities/<uuid:pk>/', activities_detail, name='trip-activities-detail'),

    path('<uuid:trip_pk>/participants/', participants_list, name='trip-participants-list'),
    path('<uuid:trip_pk>/participants/<uuid:pk>/', participants_detail, name='trip-participants-detail'),
    path('<uuid:trip_pk>/participants/<uuid:pk>/accept/', participants_accept, name='trip-participants-accept'),
    path('flights/search/', views.flight_offers, name='flight_search'),
    path('hotels/search/', views.hotel_search, name='hotel_search'),
    path('airports/search/', views.airport_search, name='airport_search'),
]