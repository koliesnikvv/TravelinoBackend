import uuid

from django.contrib.auth import get_user_model
from django.urls import reverse
from rest_framework import status
from rest_framework.test import APIClient, APITestCase
from rest_framework_simplejwt.tokens import RefreshToken

from catalog.models import City, Activity, TransportOption, AccommodationOption

User = get_user_model()


# ─────────────────────────────────────────────
# Helpers
# ─────────────────────────────────────────────

def make_verified_user(email='catalog_user@example.com', password='StrongPass1', phone='+380991111111'):
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
        short_description='Capital city.',
        ideal_durations=['Weekend', 'One week'],
        budget_level='Mid-range',
        culture=8,
        adventure=5,
        nature=4,
        beaches=1,
        nightlife=7,
        cuisine=7,
        wellness=5,
        urban=9,
        seclusion=2,
    )
    defaults.update(kwargs)
    return City.objects.create(**defaults)


def make_activity(city, **kwargs):
    defaults = dict(
        title='Museum of History',
        description='Great museum.',
        category='Culture',
    )
    defaults.update(kwargs)
    return Activity.objects.create(city=city, **defaults)


def make_transport(**kwargs):
    defaults = dict(
        departure_point='Kyiv',
        arrival_point='Lviv',
        transport_type='Bus',
        carrier_name='UkrBus',
        route_number='KL-1',
        base_price='250.00',
    )
    defaults.update(kwargs)
    return TransportOption.objects.create(**defaults)


def make_accommodation(city, **kwargs):
    defaults = dict(
        name='Grand Hotel',
        address='Main St 1',
        rating='4.5',
        description='Nice hotel.',
        price_per_night='1500.00',
    )
    defaults.update(kwargs)
    return AccommodationOption.objects.create(city=city, **defaults)


# ─────────────────────────────────────────────
# City list
# ─────────────────────────────────────────────

class CityListViewTests(APITestCase):

    def setUp(self):
        self.user = make_verified_user()
        self.client = auth_client(self.user)
        self.url = reverse('catalog:city-list')
        self.kyiv = make_city(city='Kyiv', country='Ukraine', budget_level='Mid-range', culture=8, nature=3)
        self.paris = make_city(city='Paris', country='France', budget_level='Luxury', culture=9, nature=2,
                               region='Ile-de-France', beaches=1, adventure=3, nightlife=8,
                               cuisine=9, wellness=5, urban=9, seclusion=1)

    def test_list_returns_all_cities(self):
        response = self.client.get(self.url)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        names = [c['city'] for c in response.data['results']]
        self.assertIn('Kyiv', names)
        self.assertIn('Paris', names)

    def test_search_by_city_name(self):
        response = self.client.get(self.url, {'search': 'Kyiv'})
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(len(response.data['results']), 1)
        self.assertEqual(response.data['results'][0]['city'], 'Kyiv')

    def test_search_by_country(self):
        response = self.client.get(self.url, {'search': 'France'})
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data['results'][0]['city'], 'Paris')

    def test_filter_by_budget_level(self):
        response = self.client.get(self.url, {'budget_level': 'Luxury'})
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(len(response.data['results']), 1)
        self.assertEqual(response.data['results'][0]['city'], 'Paris')

    def test_filter_by_category_culture(self):
        # culture >= 5 threshold — both cities qualify (8 and 9)
        response = self.client.get(self.url, {'categories': 'culture'})
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(len(response.data['results']), 2)

    def test_filter_by_category_nature_excludes_paris(self):
        # Kyiv nature=3, Paris nature=2 — both below threshold 5 → 0 results
        response = self.client.get(self.url, {'categories': 'nature'})
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(len(response.data['results']), 0)

    def test_filter_unknown_category_ignored(self):
        # Unknown categories are logged and ignored, not 400
        response = self.client.get(self.url, {'categories': 'unknown_cat'})
        self.assertEqual(response.status_code, status.HTTP_200_OK)

    def test_unauthenticated_can_list(self):
        # IsAuthenticatedOrReadOnly — GET is allowed without auth
        response = APIClient().get(self.url)
        self.assertEqual(response.status_code, status.HTTP_200_OK)

    def test_pagination_page_size(self):
        response = self.client.get(self.url, {'page_size': 1})
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(len(response.data['results']), 1)


# ─────────────────────────────────────────────
# City detail
# ─────────────────────────────────────────────

class CityDetailViewTests(APITestCase):

    def setUp(self):
        self.user = make_verified_user()
        self.client = auth_client(self.user)
        self.city = make_city()
        self.url = reverse('catalog:city-detail', kwargs={'pk': self.city.id})

    def test_get_city_detail(self):
        response = self.client.get(self.url)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data['city'], 'Kyiv')
        self.assertIn('culture', response.data)
        self.assertIn('budget_level', response.data)

    def test_city_detail_not_found(self):
        url = reverse('catalog:city-detail', kwargs={'pk': uuid.uuid4()})
        response = self.client.get(url)
        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)

    def test_unauthenticated_can_get_detail(self):
        response = APIClient().get(self.url)
        self.assertEqual(response.status_code, status.HTTP_200_OK)


# ─────────────────────────────────────────────
# Recommended cities
# ─────────────────────────────────────────────

class RecommendedCitiesViewTests(APITestCase):

    def setUp(self):
        self.user = make_verified_user()
        self.client = auth_client(self.user)
        self.url = reverse('catalog:city-recommended')
        make_city(city='Kyiv', culture=8, nature=4, beaches=1, adventure=5,
                  nightlife=7, cuisine=7, wellness=5, urban=9, seclusion=2)
        make_city(city='Bali', country='Indonesia', region='Asia',
                  short_description='Beach paradise.', budget_level='Budget',
                  culture=6, nature=9, beaches=10, adventure=8,
                  nightlife=5, cuisine=7, wellness=8, urban=3, seclusion=6)

    def test_recommended_no_preferences_returns_top_by_total_score(self):
        response = self.client.get(self.url)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertLessEqual(len(response.data), 10)
        # Both cities returned since we have only 2
        self.assertEqual(len(response.data), 2)

    def test_recommended_with_preferences_scores_correctly(self):
        # Set user preferences so beaches-heavy cities score higher
        self.user.profile.preferences = ['beaches', 'surfing', 'beach']
        self.user.profile.save()

        response = self.client.get(self.url)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        # Bali has beaches=10, Kyiv has beaches=1 → Bali should be first
        self.assertEqual(response.data[0]['city'], 'Bali')

    def test_recommended_with_unrecognized_preferences(self):
        # Preferences that don't map to any field — falls back to first 10
        self.user.profile.preferences = ['paragliding']
        self.user.profile.save()
        response = self.client.get(self.url)
        self.assertEqual(response.status_code, status.HTTP_200_OK)

    def test_recommended_unauthenticated_denied(self):
        response = APIClient().get(self.url)
        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)


# ─────────────────────────────────────────────
# Activity list
# ─────────────────────────────────────────────

class ActivityListViewTests(APITestCase):

    def setUp(self):
        self.user = make_verified_user()
        self.client = auth_client(self.user)
        self.url = reverse('catalog:activity-list')
        self.kyiv = make_city(city='Kyiv')
        self.paris = make_city(city='Paris', country='France', region='Ile-de-France',
                               short_description='City of light.', budget_level='Luxury',
                               culture=9, nature=2, beaches=1, adventure=3, nightlife=8,
                               cuisine=9, wellness=5, urban=9, seclusion=1)
        self.act1 = make_activity(self.kyiv, title='Lavra', category='Culture')
        self.act2 = make_activity(self.kyiv, title='Forest hike', category='Nature')
        self.act3 = make_activity(self.paris, title='Eiffel Tower', category='Culture')

    def test_list_all_activities(self):
        response = self.client.get(self.url)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(len(response.data), 3)

    def test_filter_by_city(self):
        response = self.client.get(self.url, {'city': str(self.kyiv.id)})
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(len(response.data), 2)

    def test_filter_by_category(self):
        response = self.client.get(self.url, {'category': 'Culture'})
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        titles = [a['title'] for a in response.data]
        self.assertIn('Lavra', titles)
        self.assertIn('Eiffel Tower', titles)
        self.assertNotIn('Forest hike', titles)

    def test_filter_by_city_and_category(self):
        response = self.client.get(self.url, {'city': str(self.kyiv.id), 'category': 'Nature'})
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(len(response.data), 1)
        self.assertEqual(response.data[0]['title'], 'Forest hike')

    def test_unauthenticated_can_list(self):
        response = APIClient().get(self.url)
        self.assertEqual(response.status_code, status.HTTP_200_OK)


# ─────────────────────────────────────────────
# Activity detail
# ─────────────────────────────────────────────

class ActivityDetailViewTests(APITestCase):

    def setUp(self):
        self.user = make_verified_user()
        self.client = auth_client(self.user)
        self.city = make_city()
        self.activity = make_activity(self.city)
        self.url = reverse('catalog:activity-detail', kwargs={'pk': self.activity.id})

    def test_get_activity_detail(self):
        response = self.client.get(self.url)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data['title'], 'Museum of History')
        self.assertEqual(response.data['category'], 'Culture')

    def test_activity_detail_not_found(self):
        url = reverse('catalog:activity-detail', kwargs={'pk': uuid.uuid4()})
        response = self.client.get(url)
        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)


# ─────────────────────────────────────────────
# Transport option list
# ─────────────────────────────────────────────

class TransportOptionListViewTests(APITestCase):

    def setUp(self):
        self.user = make_verified_user()
        self.client = auth_client(self.user)
        self.url = reverse('catalog:transport-list')
        self.t1 = make_transport(departure_point='Kyiv', arrival_point='Lviv',
                                  transport_type='Bus', base_price='200.00')
        self.t2 = make_transport(departure_point='Kyiv', arrival_point='Odesa',
                                  transport_type='Train', base_price='350.00', route_number='KO-2')
        self.t3 = make_transport(departure_point='Lviv', arrival_point='Warsaw',
                                  transport_type='Flight', base_price='1200.00', route_number='LW-3')

    def test_list_all_transport(self):
        response = self.client.get(self.url)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(len(response.data), 3)

    def test_filter_by_from(self):
        response = self.client.get(self.url, {'from': 'Kyiv'})
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(len(response.data), 2)

    def test_filter_by_to(self):
        response = self.client.get(self.url, {'to': 'Lviv'})
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(len(response.data), 1)

    def test_filter_by_type(self):
        response = self.client.get(self.url, {'type': 'Flight'})
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(len(response.data), 1)
        self.assertEqual(response.data[0]['transport_type'], 'Flight')

    def test_sort_by_price_asc(self):
        response = self.client.get(self.url, {'sort_by': 'base_price'})
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        prices = [float(t['base_price']) for t in response.data]
        self.assertEqual(prices, sorted(prices))

    def test_sort_by_price_desc(self):
        response = self.client.get(self.url, {'sort_by': '-base_price'})
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        prices = [float(t['base_price']) for t in response.data]
        self.assertEqual(prices, sorted(prices, reverse=True))

    def test_invalid_sort_falls_back_to_default(self):
        response = self.client.get(self.url, {'sort_by': 'invalid'})
        self.assertEqual(response.status_code, status.HTTP_200_OK)

    def test_unauthenticated_can_list(self):
        response = APIClient().get(self.url)
        self.assertEqual(response.status_code, status.HTTP_200_OK)


# ─────────────────────────────────────────────
# Transport option detail
# ─────────────────────────────────────────────

class TransportOptionDetailViewTests(APITestCase):

    def setUp(self):
        self.user = make_verified_user()
        self.client = auth_client(self.user)
        self.transport = make_transport()
        self.url = reverse('catalog:transport-detail', kwargs={'pk': self.transport.id})

    def test_get_transport_detail(self):
        response = self.client.get(self.url)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data['carrier_name'], 'UkrBus')

    def test_transport_detail_not_found(self):
        url = reverse('catalog:transport-detail', kwargs={'pk': uuid.uuid4()})
        response = self.client.get(url)
        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)


# ─────────────────────────────────────────────
# Accommodation option list
# ─────────────────────────────────────────────

class AccommodationOptionListViewTests(APITestCase):

    def setUp(self):
        self.user = make_verified_user()
        self.client = auth_client(self.user)
        self.url = reverse('catalog:accommodation-list')
        self.kyiv = make_city(city='Kyiv')
        self.paris = make_city(city='Paris', country='France', region='Ile-de-France',
                               short_description='City of light.', budget_level='Luxury',
                               culture=9, nature=2, beaches=1, adventure=3, nightlife=8,
                               cuisine=9, wellness=5, urban=9, seclusion=1)
        self.h1 = make_accommodation(self.kyiv, name='Budget Inn', price_per_night='500.00', rating='3.5')
        self.h2 = make_accommodation(self.kyiv, name='Mid Hotel', price_per_night='1500.00', rating='4.2')
        self.h3 = make_accommodation(self.paris, name='Paris Luxury', price_per_night='5000.00', rating='4.9')

    def test_list_all_accommodations(self):
        response = self.client.get(self.url)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(len(response.data), 3)

    def test_filter_by_city(self):
        response = self.client.get(self.url, {'city': str(self.kyiv.id)})
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(len(response.data), 2)

    def test_filter_by_min_price(self):
        response = self.client.get(self.url, {'min_price': '1000'})
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        names = [a['name'] for a in response.data]
        self.assertNotIn('Budget Inn', names)
        self.assertIn('Mid Hotel', names)
        self.assertIn('Paris Luxury', names)

    def test_filter_by_max_price(self):
        response = self.client.get(self.url, {'max_price': '1000'})
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        names = [a['name'] for a in response.data]
        self.assertIn('Budget Inn', names)
        self.assertNotIn('Mid Hotel', names)

    def test_filter_min_max_price(self):
        response = self.client.get(self.url, {'min_price': '1000', 'max_price': '2000'})
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(len(response.data), 1)
        self.assertEqual(response.data[0]['name'], 'Mid Hotel')

    def test_sort_by_price_asc(self):
        response = self.client.get(self.url, {'sort_by': 'price_per_night'})
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        prices = [float(a['price_per_night']) for a in response.data]
        self.assertEqual(prices, sorted(prices))

    def test_sort_by_rating_desc(self):
        response = self.client.get(self.url, {'sort_by': '-rating'})
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        ratings = [float(a['rating']) for a in response.data]
        self.assertEqual(ratings, sorted(ratings, reverse=True))

    def test_invalid_sort_falls_back_to_default(self):
        response = self.client.get(self.url, {'sort_by': 'invalid'})
        self.assertEqual(response.status_code, status.HTTP_200_OK)

    def test_invalid_price_param_ignored(self):
        response = self.client.get(self.url, {'min_price': 'notanumber'})
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(len(response.data), 3)

    def test_unauthenticated_can_list(self):
        response = APIClient().get(self.url)
        self.assertEqual(response.status_code, status.HTTP_200_OK)


# ─────────────────────────────────────────────
# Accommodation option detail
# ─────────────────────────────────────────────

class AccommodationOptionDetailViewTests(APITestCase):

    def setUp(self):
        self.user = make_verified_user()
        self.client = auth_client(self.user)
        self.city = make_city()
        self.accommodation = make_accommodation(self.city)
        self.url = reverse('catalog:accommodation-detail', kwargs={'pk': self.accommodation.id})

    def test_get_accommodation_detail(self):
        response = self.client.get(self.url)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data['name'], 'Grand Hotel')
        self.assertEqual(float(response.data['rating']), 4.5)

    def test_accommodation_detail_not_found(self):
        url = reverse('catalog:accommodation-detail', kwargs={'pk': uuid.uuid4()})
        response = self.client.get(url)
        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)