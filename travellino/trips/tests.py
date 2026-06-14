import uuid
from datetime import date, time, datetime, timezone

from django.contrib.auth import get_user_model
from django.urls import reverse
from rest_framework import status
from rest_framework.test import APIClient, APITestCase
from rest_framework_simplejwt.tokens import RefreshToken

from catalog.models import City, Activity, TransportOption, AccommodationOption
from trips.models import (
    Trip, TransportBooking, AccommodationBooking,
    TripActivity, TripParticipant, AccessLevel, InviteStatus,
)

User = get_user_model()


# ─────────────────────────────────────────────
# Helpers
# ─────────────────────────────────────────────

_phone_counter = [0]

def make_verified_user(email=None, password='StrongPass1', phone=None):
    _phone_counter[0] += 1
    if email is None:
        email = f'user{_phone_counter[0]}@example.com'
    if phone is None:
        phone = f'+38099{_phone_counter[0]:07d}'
    user = User.objects.create_user(
        email=email,
        password=password,
        phone=phone,
        first_name='Test',
        last_name='User',
    )
    user.is_active = True
    user.is_email_verified = True
    user.save()
    return user


def auth_client(user):
    client = APIClient()
    refresh = RefreshToken.for_user(user)
    client.credentials(HTTP_AUTHORIZATION=f'Bearer {refresh.access_token}')
    return client


def make_city(**kwargs):
    defaults = dict(
        city='Kyiv',
        country='Ukraine',
        region='Central',
        short_description='Capital.',
        ideal_durations=['Weekend'],
        budget_level='Mid-range',
        culture=7, adventure=5, nature=4, beaches=1,
        nightlife=6, cuisine=7, wellness=5, urban=8, seclusion=2,
    )
    defaults.update(kwargs)
    return City.objects.create(**defaults)


def make_trip(owner, city=None, **kwargs):
    if city is None:
        city = make_city()
    defaults = dict(
        title='Test Trip',
        start_date=date(2025, 8, 1),
        end_date=date(2025, 8, 10),
    )
    defaults.update(kwargs)
    return Trip.objects.create(owner=owner, city=city, **defaults)


def make_transport_option(**kwargs):
    defaults = dict(
        departure_point='Kyiv',
        arrival_point='Lviv',
        transport_type='Bus',
        carrier_name='UkrBus',
        route_number='KL-1',
        base_price='200.00',
    )
    defaults.update(kwargs)
    return TransportOption.objects.create(**defaults)


def make_accommodation_option(city, **kwargs):
    defaults = dict(
        name='Test Hotel',
        address='Street 1',
        rating='4.0',
        description='Nice.',
        price_per_night='1000.00',
    )
    defaults.update(kwargs)
    return AccommodationOption.objects.create(city=city, **defaults)


def make_activity_catalog(city, **kwargs):
    defaults = dict(
        title='City Tour',
        description='Walking tour.',
        category='Culture',
    )
    defaults.update(kwargs)
    return Activity.objects.create(city=city, **defaults)


# ─────────────────────────────────────────────
# Trip CRUD
# ─────────────────────────────────────────────

class TripListCreateViewTests(APITestCase):

    def setUp(self):
        self.owner = make_verified_user()
        self.client = auth_client(self.owner)
        self.city = make_city()
        self.url = reverse('trip-list')

    def test_create_trip(self):
        response = self.client.post(self.url, {
            'title': 'Summer Trip',
            'city': str(self.city.id),
            'start_date': '2025-07-01',
            'end_date': '2025-07-10',
        })
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertEqual(response.data['title'], 'Summer Trip')
        # owner is set automatically
        self.assertEqual(Trip.objects.count(), 1)
        self.assertEqual(Trip.objects.first().owner, self.owner)

    def test_list_trips_owner_sees_own(self):
        make_trip(self.owner, self.city, title='My Trip')
        other_user = make_verified_user()
        make_trip(other_user, self.city, title='Other Trip')

        response = self.client.get(self.url)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        titles = [t['title'] for t in response.data]
        self.assertIn('My Trip', titles)
        self.assertNotIn('Other Trip', titles)

    def test_participant_sees_shared_trip(self):
        other_user = make_verified_user()
        trip = make_trip(other_user, self.city, title='Shared Trip')
        TripParticipant.objects.create(
            trip=trip,
            user=self.owner,
            invitee_email=self.owner.email,
            access_level=AccessLevel.VIEW,
            status=InviteStatus.ACCEPTED,
        )
        response = self.client.get(self.url)
        titles = [t['title'] for t in response.data]
        self.assertIn('Shared Trip', titles)

    def test_pending_participant_does_not_see_trip(self):
        other_user = make_verified_user()
        trip = make_trip(other_user, self.city, title='Not Yet Shared')
        TripParticipant.objects.create(
            trip=trip,
            user=self.owner,
            invitee_email=self.owner.email,
            access_level=AccessLevel.VIEW,
            status=InviteStatus.PENDING,
        )
        response = self.client.get(self.url)
        titles = [t['title'] for t in response.data]
        self.assertNotIn('Not Yet Shared', titles)

    def test_create_trip_unauthenticated(self):
        response = APIClient().post(self.url, {
            'title': 'Trip',
            'city': str(self.city.id),
            'start_date': '2025-07-01',
            'end_date': '2025-07-10',
        })
        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)


class TripDetailUpdateDeleteViewTests(APITestCase):

    def setUp(self):
        self.owner = make_verified_user()
        self.client = auth_client(self.owner)
        self.city = make_city()
        self.trip = make_trip(self.owner, self.city)

    def _url(self, pk=None):
        return reverse('trip-detail', kwargs={'pk': pk or self.trip.id})

    def test_retrieve_trip_returns_detail_serializer(self):
        response = self.client.get(self._url())
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        # TripDetailSerializer fields
        self.assertIn('transport', response.data)
        self.assertIn('accommodation', response.data)
        self.assertIn('activities', response.data)
        self.assertIn('participants', response.data)
        self.assertIn('current_user_role', response.data)
        self.assertEqual(response.data['current_user_role'], 'owner')

    def test_retrieve_trip_not_found(self):
        response = self.client.get(self._url(uuid.uuid4()))
        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)

    def test_partial_update_trip(self):
        response = self.client.patch(self._url(), {'title': 'Updated Title'})
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data['title'], 'Updated Title')

    def test_non_owner_cannot_update(self):
        other = make_verified_user()
        client = auth_client(other)
        # Make other an accepted participant so they can see the trip
        TripParticipant.objects.create(
            trip=self.trip,
            user=other,
            invitee_email=other.email,
            access_level=AccessLevel.EDIT,
            status=InviteStatus.ACCEPTED,
        )
        response = client.patch(self._url(), {'title': 'Hacked'})
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)

    def test_delete_trip(self):
        response = self.client.delete(self._url())
        self.assertEqual(response.status_code, status.HTTP_204_NO_CONTENT)
        self.assertFalse(Trip.objects.filter(id=self.trip.id).exists())

    def test_non_owner_cannot_delete(self):
        other = make_verified_user()
        client = auth_client(other)
        TripParticipant.objects.create(
            trip=self.trip,
            user=other,
            invitee_email=other.email,
            access_level=AccessLevel.EDIT,
            status=InviteStatus.ACCEPTED,
        )
        response = client.delete(self._url())
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)

    def test_current_user_role_edit_participant(self):
        other = make_verified_user()
        TripParticipant.objects.create(
            trip=self.trip,
            user=other,
            invitee_email=other.email,
            access_level=AccessLevel.EDIT,
            status=InviteStatus.ACCEPTED,
        )
        client = auth_client(other)
        response = client.get(self._url())
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data['current_user_role'], 'edit')

    def test_current_user_role_view_participant(self):
        other = make_verified_user()
        TripParticipant.objects.create(
            trip=self.trip,
            user=other,
            invitee_email=other.email,
            access_level=AccessLevel.VIEW,
            status=InviteStatus.ACCEPTED,
        )
        client = auth_client(other)
        response = client.get(self._url())
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data['current_user_role'], 'view')


# ─────────────────────────────────────────────
# Transport bookings
# ─────────────────────────────────────────────

class TransportBookingViewSetTests(APITestCase):

    def setUp(self):
        self.owner = make_verified_user()
        self.client = auth_client(self.owner)
        self.city = make_city()
        self.trip = make_trip(self.owner, self.city)
        self.transport_option = make_transport_option()

        self.list_url = reverse('trip-transport-list', kwargs={'trip_pk': self.trip.id})

    def _detail_url(self, pk):
        return reverse('trip-transport-detail', kwargs={'trip_pk': self.trip.id, 'pk': pk})

    def _booking_payload(self):
        return {
            'departure_point': 'Kyiv',
            'arrival_point': 'Lviv',
            'departure_datetime': '2025-08-01T10:00:00Z',
            'arrival_datetime': '2025-08-01T14:00:00Z',
            'price': '350.00',
            'passengers_count': 2,
            'transport_option': str(self.transport_option.id),
        }

    def test_create_transport_booking(self):
        response = self.client.post(self.list_url, self._booking_payload())
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertEqual(TransportBooking.objects.count(), 1)
        self.assertEqual(TransportBooking.objects.first().trip, self.trip)

    def test_list_transport_bookings(self):
        TransportBooking.objects.create(
            trip=self.trip,
            departure_point='Kyiv',
            arrival_point='Lviv',
            departure_datetime=datetime(2025, 8, 1, 10, 0, tzinfo=timezone.utc),
            arrival_datetime=datetime(2025, 8, 1, 14, 0, tzinfo=timezone.utc),
            price='350.00',
            passengers_count=1,
        )
        response = self.client.get(self.list_url)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(len(response.data), 1)

    def test_retrieve_transport_booking_returns_detail_serializer(self):
        booking = TransportBooking.objects.create(
            trip=self.trip,
            departure_point='Kyiv',
            arrival_point='Lviv',
            departure_datetime=datetime(2025, 8, 1, 10, 0, tzinfo=timezone.utc),
            arrival_datetime=datetime(2025, 8, 1, 14, 0, tzinfo=timezone.utc),
            price='350.00',
            passengers_count=1,
            transport_option=self.transport_option,
        )
        response = self.client.get(self._detail_url(booking.id))
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        # TransportBookingDetailSerializer nests transport_option as object
        self.assertIsInstance(response.data['transport_option'], dict)
        self.assertEqual(response.data['transport_option']['carrier_name'], 'UkrBus')

    def test_delete_transport_booking(self):
        booking = TransportBooking.objects.create(
            trip=self.trip,
            departure_point='Kyiv',
            arrival_point='Lviv',
            departure_datetime=datetime(2025, 8, 1, 10, 0, tzinfo=timezone.utc),
            arrival_datetime=datetime(2025, 8, 1, 14, 0, tzinfo=timezone.utc),
            price='350.00',
            passengers_count=1,
        )
        response = self.client.delete(self._detail_url(booking.id))
        self.assertEqual(response.status_code, status.HTTP_204_NO_CONTENT)
        self.assertFalse(TransportBooking.objects.filter(id=booking.id).exists())

    def test_view_participant_cannot_create(self):
        other = make_verified_user()
        TripParticipant.objects.create(
            trip=self.trip,
            user=other,
            invitee_email=other.email,
            access_level=AccessLevel.VIEW,
            status=InviteStatus.ACCEPTED,
        )
        client = auth_client(other)
        response = client.post(self.list_url, self._booking_payload())
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)

    def test_edit_participant_can_create(self):
        other = make_verified_user()
        TripParticipant.objects.create(
            trip=self.trip,
            user=other,
            invitee_email=other.email,
            access_level=AccessLevel.EDIT,
            status=InviteStatus.ACCEPTED,
        )
        client = auth_client(other)
        response = client.post(self.list_url, self._booking_payload())
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)

    def test_non_participant_cannot_access(self):
        other = make_verified_user()
        client = auth_client(other)
        response = client.get(self.list_url)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(len(response.data), 0)  # empty queryset, not 403


# ─────────────────────────────────────────────
# Accommodation bookings
# ─────────────────────────────────────────────

class AccommodationBookingViewSetTests(APITestCase):

    def setUp(self):
        self.owner = make_verified_user()
        self.client = auth_client(self.owner)
        self.city = make_city()
        self.trip = make_trip(self.owner, self.city)
        self.accommodation_option = make_accommodation_option(self.city)
        self.list_url = reverse('trip-accommodation-list', kwargs={'trip_pk': self.trip.id})

    def _detail_url(self, pk):
        return reverse('trip-accommodation-detail', kwargs={'trip_pk': self.trip.id, 'pk': pk})

    def _booking_payload(self):
        return {
            'accommodation_name': 'Test Hotel',
            'check_in_date': '2025-08-01',
            'check_out_date': '2025-08-05',
            'price_per_night': '1000.00',
            'total_price': '4000.00',
            'accommodation_option': str(self.accommodation_option.id),
        }

    def test_create_accommodation_booking(self):
        response = self.client.post(self.list_url, self._booking_payload())
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertEqual(AccommodationBooking.objects.count(), 1)

    def test_list_accommodation_bookings(self):
        AccommodationBooking.objects.create(
            trip=self.trip,
            accommodation_name='Test Hotel',
            check_in_date=date(2025, 8, 1),
            check_out_date=date(2025, 8, 5),
            price_per_night='1000.00',
            total_price='4000.00',
        )
        response = self.client.get(self.list_url)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(len(response.data), 1)

    def test_retrieve_accommodation_booking_detail(self):
        booking = AccommodationBooking.objects.create(
            trip=self.trip,
            accommodation_name='Test Hotel',
            check_in_date=date(2025, 8, 1),
            check_out_date=date(2025, 8, 5),
            price_per_night='1000.00',
            total_price='4000.00',
            accommodation_option=self.accommodation_option,
        )
        response = self.client.get(self._detail_url(booking.id))
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIsInstance(response.data['accommodation_option'], dict)
        self.assertEqual(response.data['accommodation_option']['name'], 'Test Hotel')

    def test_delete_accommodation_booking(self):
        booking = AccommodationBooking.objects.create(
            trip=self.trip,
            accommodation_name='Test Hotel',
            check_in_date=date(2025, 8, 1),
            check_out_date=date(2025, 8, 5),
            price_per_night='1000.00',
            total_price='4000.00',
        )
        response = self.client.delete(self._detail_url(booking.id))
        self.assertEqual(response.status_code, status.HTTP_204_NO_CONTENT)

    def test_view_participant_cannot_create(self):
        other = make_verified_user()
        TripParticipant.objects.create(
            trip=self.trip,
            user=other,
            invitee_email=other.email,
            access_level=AccessLevel.VIEW,
            status=InviteStatus.ACCEPTED,
        )
        response = auth_client(other).post(self.list_url, self._booking_payload())
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)


# ─────────────────────────────────────────────
# Trip activities
# ─────────────────────────────────────────────

class TripActivityViewSetTests(APITestCase):

    def setUp(self):
        self.owner = make_verified_user()
        self.client = auth_client(self.owner)
        self.city = make_city()
        self.trip = make_trip(self.owner, self.city)
        self.catalog_activity = make_activity_catalog(self.city)
        self.list_url = reverse('trip-activities-list', kwargs={'trip_pk': self.trip.id})

    def _detail_url(self, pk):
        return reverse('trip-activities-detail', kwargs={'trip_pk': self.trip.id, 'pk': pk})

    def _activity_payload(self):
        return {
            'activity': str(self.catalog_activity.id),
            'scheduled_date': '2025-08-03',
            'start_time': '10:00:00',
            'end_time': '12:00:00',
        }

    def test_create_trip_activity(self):
        response = self.client.post(self.list_url, self._activity_payload())
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertEqual(TripActivity.objects.count(), 1)

    def test_list_trip_activities(self):
        TripActivity.objects.create(
            trip=self.trip,
            activity=self.catalog_activity,
            scheduled_date=date(2025, 8, 3),
            start_time=time(10, 0),
            end_time=time(12, 0),
        )
        response = self.client.get(self.list_url)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(len(response.data), 1)

    def test_retrieve_trip_activity_detail(self):
        ta = TripActivity.objects.create(
            trip=self.trip,
            activity=self.catalog_activity,
            scheduled_date=date(2025, 8, 3),
            start_time=time(10, 0),
            end_time=time(12, 0),
        )
        response = self.client.get(self._detail_url(ta.id))
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        # TripActivityDetailSerializer nests activity as object
        self.assertIsInstance(response.data['activity'], dict)
        self.assertEqual(response.data['activity_title'], 'City Tour')

    def test_activity_title_fallback_when_activity_is_none(self):
        ta = TripActivity.objects.create(
            trip=self.trip,
            activity=None,
            scheduled_date=date(2025, 8, 3),
            start_time=time(10, 0),
            end_time=time(12, 0),
        )
        response = self.client.get(self.list_url)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data[0]['activity_title'], 'Custom Activity')

    def test_delete_trip_activity(self):
        ta = TripActivity.objects.create(
            trip=self.trip,
            activity=self.catalog_activity,
            scheduled_date=date(2025, 8, 3),
            start_time=time(10, 0),
            end_time=time(12, 0),
        )
        response = self.client.delete(self._detail_url(ta.id))
        self.assertEqual(response.status_code, status.HTTP_204_NO_CONTENT)

    def test_view_participant_cannot_create(self):
        other = make_verified_user()
        TripParticipant.objects.create(
            trip=self.trip,
            user=other,
            invitee_email=other.email,
            access_level=AccessLevel.VIEW,
            status=InviteStatus.ACCEPTED,
        )
        response = auth_client(other).post(self.list_url, self._activity_payload())
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)

    def test_edit_participant_can_create(self):
        other = make_verified_user()
        TripParticipant.objects.create(
            trip=self.trip,
            user=other,
            invitee_email=other.email,
            access_level=AccessLevel.EDIT,
            status=InviteStatus.ACCEPTED,
        )
        response = auth_client(other).post(self.list_url, self._activity_payload())
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)


# ─────────────────────────────────────────────
# Trip participants
# ─────────────────────────────────────────────

class TripParticipantViewSetTests(APITestCase):

    def setUp(self):
        self.owner = make_verified_user()
        self.client = auth_client(self.owner)
        self.city = make_city()
        self.trip = make_trip(self.owner, self.city)
        self.list_url = reverse('trip-participants-list', kwargs={'trip_pk': self.trip.id})

    def _detail_url(self, pk):
        return reverse('trip-participants-detail', kwargs={'trip_pk': self.trip.id, 'pk': pk})

    def _accept_url(self, pk):
        return reverse('trip-participants-accept', kwargs={'trip_pk': self.trip.id, 'pk': pk})

    def test_owner_can_invite_participant(self):
        with self.settings(EMAIL_BACKEND='django.core.mail.backends.locmem.EmailBackend'):
            response = self.client.post(self.list_url, {
                'invitee_email': 'guest@example.com',
                'access_level': 'Edit',
            })
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertTrue(TripParticipant.objects.filter(invitee_email='guest@example.com').exists())

    def test_non_owner_cannot_invite(self):
        other = make_verified_user()
        TripParticipant.objects.create(
            trip=self.trip,
            user=other,
            invitee_email=other.email,
            access_level=AccessLevel.EDIT,
            status=InviteStatus.ACCEPTED,
        )
        with self.settings(EMAIL_BACKEND='django.core.mail.backends.locmem.EmailBackend'):
            response = auth_client(other).post(self.list_url, {
                'invitee_email': 'another@example.com',
                'access_level': 'View',
            })
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)

    def test_list_participants(self):
        TripParticipant.objects.create(
            trip=self.trip,
            invitee_email='guest@example.com',
            access_level=AccessLevel.VIEW,
            status=InviteStatus.PENDING,
        )
        response = self.client.get(self.list_url)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(len(response.data), 1)

    def test_owner_can_delete_participant(self):
        participant = TripParticipant.objects.create(
            trip=self.trip,
            invitee_email='guest@example.com',
            access_level=AccessLevel.VIEW,
            status=InviteStatus.PENDING,
        )
        response = self.client.delete(self._detail_url(participant.id))
        self.assertEqual(response.status_code, status.HTTP_204_NO_CONTENT)
        self.assertFalse(TripParticipant.objects.filter(id=participant.id).exists())

    def test_non_owner_cannot_delete_participant(self):
        other = make_verified_user()
        TripParticipant.objects.create(
            trip=self.trip,
            user=other,
            invitee_email=other.email,
            access_level=AccessLevel.EDIT,
            status=InviteStatus.ACCEPTED,
        )
        participant = TripParticipant.objects.create(
            trip=self.trip,
            invitee_email='third@example.com',
            access_level=AccessLevel.VIEW,
            status=InviteStatus.PENDING,
        )
        response = auth_client(other).delete(self._detail_url(participant.id))
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)


# ─────────────────────────────────────────────
# Accept invite
# ─────────────────────────────────────────────

class AcceptInviteTests(APITestCase):

    def setUp(self):
        self.owner = make_verified_user()
        self.city = make_city()
        self.trip = make_trip(self.owner, self.city)

    def _accept_url(self, trip_id, participant_id):
        return reverse('trip-participants-accept', kwargs={
            'trip_pk': trip_id,
            'pk': participant_id,
        })

    def test_invitee_can_accept_invite(self):
        invitee = make_verified_user()
        participant = TripParticipant.objects.create(
            trip=self.trip,
            invitee_email=invitee.email,
            access_level=AccessLevel.EDIT,
            status=InviteStatus.PENDING,
        )
        response = auth_client(invitee).post(self._accept_url(self.trip.id, participant.id))
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        participant.refresh_from_db()
        self.assertEqual(participant.status, InviteStatus.ACCEPTED)
        self.assertEqual(participant.user, invitee)

    def test_wrong_user_cannot_accept_invite(self):
        invitee = make_verified_user()
        wrong_user = make_verified_user()
        participant = TripParticipant.objects.create(
            trip=self.trip,
            invitee_email=invitee.email,
            access_level=AccessLevel.EDIT,
            status=InviteStatus.PENDING,
        )
        response = auth_client(wrong_user).post(self._accept_url(self.trip.id, participant.id))
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)
        participant.refresh_from_db()
        self.assertEqual(participant.status, InviteStatus.PENDING)

    def test_unauthenticated_cannot_accept(self):
        participant = TripParticipant.objects.create(
            trip=self.trip,
            invitee_email='guest@example.com',
            access_level=AccessLevel.EDIT,
            status=InviteStatus.PENDING,
        )
        response = APIClient().post(self._accept_url(self.trip.id, participant.id))
        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)


# ─────────────────────────────────────────────
# ICS export
# ─────────────────────────────────────────────

class TripExportICSTests(APITestCase):

    def setUp(self):
        self.owner = make_verified_user()
        self.client = auth_client(self.owner)
        self.city = make_city()
        self.trip = make_trip(self.owner, self.city,
                              start_date=date(2025, 8, 1),
                              end_date=date(2025, 8, 10))
        self.catalog_activity = make_activity_catalog(self.city)
        self.transport_option = make_transport_option()
        self.accommodation_option = make_accommodation_option(self.city)

        TripActivity.objects.create(
            trip=self.trip,
            activity=self.catalog_activity,
            scheduled_date=date(2025, 8, 3),
            start_time=time(10, 0),
            end_time=time(12, 0),
        )
        TransportBooking.objects.create(
            trip=self.trip,
            departure_point='Kyiv',
            arrival_point='Lviv',
            departure_datetime=datetime(2025, 8, 1, 10, 0, tzinfo=timezone.utc),
            arrival_datetime=datetime(2025, 8, 1, 14, 0, tzinfo=timezone.utc),
            price='350.00',
            passengers_count=1,
            transport_option=self.transport_option,
        )
        AccommodationBooking.objects.create(
            trip=self.trip,
            accommodation_name='Test Hotel',
            check_in_date=date(2025, 8, 1),
            check_out_date=date(2025, 8, 5),
            price_per_night='1000.00',
            total_price='4000.00',
        )

        self.url = reverse('trip-export-ics', kwargs={'pk': self.trip.id})

    def test_export_returns_ics_content_type(self):
        response = self.client.get(self.url)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIn('text/calendar', response['Content-Type'])

    def test_export_contains_all_components_by_default(self):
        response = self.client.get(self.url)
        content = response.content.decode()
        self.assertIn('BEGIN:VCALENDAR', content)
        # activity
        self.assertIn('City Tour', content)
        # transport
        self.assertIn('Kyiv', content)
        # accommodation
        self.assertIn('Test Hotel', content)

    def test_export_activities_only(self):
        response = self.client.get(self.url, {'activities': 'true', 'transport': 'false', 'accommodation': 'false'})
        content = response.content.decode()
        self.assertIn('City Tour', content)
        self.assertNotIn('Test Hotel', content)
        self.assertNotIn('Kyiv \u2192 Lviv', content)

    def test_export_transport_only(self):
        response = self.client.get(self.url, {'activities': 'false', 'transport': 'true', 'accommodation': 'false'})
        content = response.content.decode()
        self.assertNotIn('City Tour', content)
        self.assertNotIn('Test Hotel', content)
        self.assertIn('Kyiv', content)

    def test_export_accommodation_only(self):
        response = self.client.get(self.url, {'activities': 'false', 'transport': 'false', 'accommodation': 'true'})
        content = response.content.decode()
        self.assertNotIn('City Tour', content)
        self.assertIn('Test Hotel', content)

    def test_export_content_disposition_header(self):
        response = self.client.get(self.url)
        self.assertIn('attachment', response['Content-Disposition'])
        self.assertIn('.ics', response['Content-Disposition'])

    def test_export_unauthenticated_denied(self):
        response = APIClient().get(self.url)
        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)

    def test_export_non_participant_gets_404(self):
        other = make_verified_user()
        url = reverse('trip-export-ics', kwargs={'pk': self.trip.id})
        response = auth_client(other).get(url)
        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)