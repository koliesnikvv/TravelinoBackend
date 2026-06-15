from django.db.models import Q
from django.http import HttpResponse
from datetime import datetime, timedelta
from icalendar import Calendar, Event
from rest_framework import viewsets, status
from rest_framework.decorators import action
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response

from users.utils import send_invite_email
from .models import (
    Trip, TransportBooking, AccommodationBooking,
    TripActivity, TripParticipant, AccessLevel, InviteStatus
)
from .serializers import (
    TripSerializer, TripDetailSerializer,
    TransportBookingSerializer, TransportBookingDetailSerializer,
    AccommodationBookingSerializer, AccommodationBookingDetailSerializer,
    TripActivitySerializer, TripActivityDetailSerializer,
    TripParticipantSerializer,
)


class TripViewSet(viewsets.ModelViewSet):
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        user = self.request.user
        # trips where user is owner OR accepted participant
        return Trip.objects.filter(
            Q(owner=user) |
            Q(participants__user=user, participants__status=InviteStatus.ACCEPTED)
        ).distinct()

    def get_serializer_class(self):
        # retrieve = GET /api/trips/{id}/ -> full detail with nested transport/accommodation/activities
        # update/partial_update = PATCH /api/trips/{id}/ -> also return full detail so frontend state isn't overwritten
        # all other actions -> basic serializer
        if self.action in ['retrieve', 'update', 'partial_update']:
            return TripDetailSerializer
        return TripSerializer

    def perform_create(self, serializer):
        # automatically set owner to the currently authenticated user on POST /api/trips/
        serializer.save(owner=self.request.user)

    def update(self, request, *args, **kwargs):
        trip = self.get_object()
        if trip.owner != request.user:
            return Response(
                {'detail': 'Only the owner can edit this trip.'},
                status=status.HTTP_403_FORBIDDEN
            )
        return super().update(request, *args, **kwargs)

    def destroy(self, request, *args, **kwargs):
        trip = self.get_object()
        if trip.owner != request.user:
            return Response(
                {'detail': 'Only the owner can delete this trip.'},
                status=status.HTTP_403_FORBIDDEN
            )
        return super().destroy(request, *args, **kwargs)

    @action(detail=True, methods=['get'], url_path='export')
    def export_ics(self, request, pk=None):
        # GET /api/trips/{pk}/export/?activities=true&transport=true&accommodation=true
        # Query params are strings — compare against 'true' explicitly.
        # Missing param defaults to True so omitting it is the same as including it.
        trip = self.get_object()

        include_activities = request.query_params.get('activities', 'true') == 'true'
        include_transport = request.query_params.get('transport', 'true') == 'true'
        include_accommodation = request.query_params.get('accommodation', 'true') == 'true'

        cal = Calendar()
        cal.add('prodid', '-//Travellino//EN')
        cal.add('version', '2.0')
        cal.add('calscale', 'GREGORIAN')
        cal.add('method', 'PUBLISH')

        if include_activities:
            for a in trip.activities.select_related('activity').all():
                ev = Event()
                ev.add('uid', f'activity-{a.id}@travellino')
                ev.add('summary', a.activity.title if a.activity else (a.activity_name or 'Activity'))
                # start_time / end_time are TimeField — stored without timezone (local time).
                # Use naive datetime (no tzinfo) so the calendar displays the time as-is,
                # without any UTC conversion ("floating" time per RFC 5545).
                ev.add('dtstart', datetime.combine(a.scheduled_date, a.start_time))
                end_date = a.scheduled_date if a.end_time >= a.start_time else a.scheduled_date + timedelta(days=1)
                ev.add("dtend", datetime.combine(end_date, a.end_time))
                cal.add_component(ev)

        if include_transport:
            for t in trip.transport_bookings.all():
                ev = Event()
                ev.add('uid', f'transport-{t.id}@travellino')
                ev.add('summary', f'{t.departure_point} → {t.arrival_point}')
                # departure_datetime / arrival_datetime are DateTimeField —
                # Django returns timezone-aware objects when USE_TZ=True. Keep as-is.
                ev.add('dtstart', t.departure_datetime)
                ev.add('dtend', t.arrival_datetime)
                if t.transport_option and t.transport_option.carrier_name:
                    ev.add('description', t.transport_option.carrier_name)
                cal.add_component(ev)

        if include_accommodation:
            for a in trip.accommodation_bookings.all():
                ev = Event()
                ev.add('uid', f'accommodation-{a.id}@travellino')
                ev.add('summary', a.accommodation_name)
                # All-day events use date objects — icalendar sets VALUE=DATE automatically.
                ev.add('dtstart', a.check_in_date)
                # DTEND for VALUE=DATE is exclusive per RFC 5545.
                # check_out_date is the actual checkout day, so add 1 day
                # so the event visually spans through that day in the calendar.
                ev.add('dtend', a.check_out_date + timedelta(days=1))
                cal.add_component(ev)

        filename = f'{trip.title}.ics'
        response = HttpResponse(cal.to_ical(), content_type='text/calendar; charset=utf-8')
        response['Content-Disposition'] = f'attachment; filename="{filename}"'
        return response


class NestedTripViewSet(viewsets.ModelViewSet):
    """
    Base class for ViewSets that are nested under a Trip.
    Provides _check_edit_permission used by Transport, Accommodation, Activity.
    """
    permission_classes = [IsAuthenticated]

    def _get_trip_for_user(self, user):
        """
        Returns the trip if the user is owner or accepted participant.
        Otherwise returns None.
        Used by get_queryset to prevent unauthorized access to nested resources.
        """
        return Trip.objects.filter(
            Q(id=self.kwargs['trip_pk']) &
            (Q(owner=user) | Q(participants__user=user, participants__status=InviteStatus.ACCEPTED))
        ).first()

    def _check_edit_permission(self, user):
        trip = self._get_trip_for_user(user)
        if not trip:
            return None, Response({'detail': 'Trip not found.'}, status=status.HTTP_404_NOT_FOUND)

        is_owner = trip.owner == user
        is_editor = TripParticipant.objects.filter(
            trip=trip,
            user=user,
            access_level=AccessLevel.EDIT,
            status=InviteStatus.ACCEPTED
        ).exists()

        if not (is_owner or is_editor):
            return None, Response({'detail': 'Permission denied.'}, status=status.HTTP_403_FORBIDDEN)

        return trip, None

    def perform_create(self, serializer):
        trip = Trip.objects.get(pk=self.kwargs['trip_pk'])
        serializer.save(trip=trip)

    def create(self, request, *args, **kwargs):
        _, err = self._check_edit_permission(request.user)
        if err:
            return err
        return super().create(request, *args, **kwargs)

    def update(self, request, *args, **kwargs):
        _, err = self._check_edit_permission(request.user)
        if err:
            return err
        return super().update(request, *args, **kwargs)

    def destroy(self, request, *args, **kwargs):
        _, err = self._check_edit_permission(request.user)
        if err:
            return err
        return super().destroy(request, *args, **kwargs)


class TransportBookingViewSet(NestedTripViewSet):

    def get_queryset(self):
        user = self.request.user
        # only return data if user has access to this trip (owner or accepted participant)
        if not self._get_trip_for_user(user):
            return TransportBooking.objects.none()
        return TransportBooking.objects.filter(trip__id=self.kwargs['trip_pk'])

    def get_serializer_class(self):
        if self.action == 'retrieve':
            return TransportBookingDetailSerializer
        return TransportBookingSerializer


class AccommodationBookingViewSet(NestedTripViewSet):

    def get_queryset(self):
        user = self.request.user
        # only return data if user has access to this trip (owner or accepted participant)
        if not self._get_trip_for_user(user):
            return AccommodationBooking.objects.none()
        return AccommodationBooking.objects.filter(trip__id=self.kwargs['trip_pk'])

    def get_serializer_class(self):
        if self.action == 'retrieve':
            return AccommodationBookingDetailSerializer
        return AccommodationBookingSerializer


class TripActivityViewSet(NestedTripViewSet):

    def get_queryset(self):
        user = self.request.user
        # only return data if user has access to this trip (owner or accepted participant)
        if not self._get_trip_for_user(user):
            return TripActivity.objects.none()
        return TripActivity.objects.filter(trip__id=self.kwargs['trip_pk'])

    def get_serializer_class(self):
        if self.action == 'retrieve':
            return TripActivityDetailSerializer
        return TripActivitySerializer


class TripParticipantViewSet(viewsets.ModelViewSet):
    permission_classes = [IsAuthenticated]
    serializer_class = TripParticipantSerializer

    def get_queryset(self):
        return TripParticipant.objects.filter(trip__id=self.kwargs['trip_pk'])

    def _check_owner(self, user):
        try:
            trip = Trip.objects.get(pk=self.kwargs['trip_pk'])
        except Trip.DoesNotExist:
            return None, Response({'detail': 'Trip not found.'}, status=status.HTTP_404_NOT_FOUND)

        if trip.owner != user:
            return None, Response(
                {'detail': 'Only the owner can manage participants.'},
                status=status.HTTP_403_FORBIDDEN
            )
        return trip, None

    def perform_create(self, serializer):
        trip = Trip.objects.get(pk=self.kwargs['trip_pk'])
        participant = serializer.save(trip=trip)
        send_invite_email(participant.invitee_email, trip, participant.id)

    def create(self, request, *args, **kwargs):
        _, err = self._check_owner(request.user)
        if err:
            return err
        return super().create(request, *args, **kwargs)

    def destroy(self, request, *args, **kwargs):
        _, err = self._check_owner(request.user)
        if err:
            return err
        return super().destroy(request, *args, **kwargs)

    @action(detail=True, methods=['post'], url_path='accept')
    def accept_invite(self, request, trip_pk=None, pk=None):
        # POST /api/trips/{trip_pk}/participants/{pk}/accept/
        # check by email — participant.user is None until invite is accepted
        participant = self.get_object()

        if participant.invitee_email != request.user.email:
            return Response(
                {'detail': 'You can only accept your own invite.'},
                status=status.HTTP_403_FORBIDDEN
            )

        # link the user account to the participant record
        participant.user = request.user
        participant.status = InviteStatus.ACCEPTED
        participant.save()

        return Response(TripParticipantSerializer(participant).data)