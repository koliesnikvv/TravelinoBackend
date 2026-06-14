import logging

from django.core.cache import cache
from django.db.models import Q
from rest_framework import generics, permissions
from rest_framework.pagination import PageNumberPagination
from rest_framework.response import Response
from rest_framework.views import APIView

from .models import City, Activity, TransportOption, AccommodationOption
from .serializers import (
    CitySerializer,
    ActivitySerializer,
    TransportOptionSerializer,
    AccommodationOptionSerializer,
)

logger = logging.getLogger(__name__)


CATEGORY_SCORE_THRESHOLD = 5

VALID_CATEGORY_FIELDS = [
    'culture', 'adventure', 'nature', 'beaches',
    'nightlife', 'cuisine', 'wellness', 'urban', 'seclusion',
]

PREFERENCE_TO_FIELD = {
    'museums':       'culture',
    'architecture':  'culture',
    'history':       'culture',
    'photography':   'culture',
    'beaches':       'beaches',
    'surfing':       'beaches',
    'beach':         'beaches',
    'seafood':       'cuisine',
    'coffee':        'cuisine',
    'street-food':   'cuisine',
    'hiking':        'nature',
    'mountains':     'nature',
    'nature':        'nature',
    'shopping':      'urban',
    'city':          'urban',
    'nightlife':     'nightlife',
    'wellness':      'wellness',
    'asia':          'adventure',
}

VALID_SORT_TRANSPORT = ['base_price', '-base_price']
VALID_SORT_ACCOMMODATION = ['price_per_night', '-price_per_night', 'rating', '-rating']


class CityPagination(PageNumberPagination):
    page_size = 12
    page_size_query_param = 'page_size'
    max_page_size = 50


class CityListView(generics.ListAPIView):
    """
    GET /api/catalog/cities/
    """
    serializer_class = CitySerializer
    permission_classes = [permissions.IsAuthenticatedOrReadOnly]
    pagination_class = CityPagination

    def get_queryset(self):
        qs = City.objects.all()

        search = self.request.query_params.get('search', '').strip()
        if search:
            qs = qs.filter(
                Q(city__icontains=search) | Q(country__icontains=search)
            )

        budget_level = self.request.query_params.get('budget_level', '').strip()
        if budget_level:
            qs = qs.filter(budget_level=budget_level)

        categories_param = self.request.query_params.get('categories', '').strip()
        if categories_param:
            categories = [c.strip() for c in categories_param.split(',')]
            for cat in categories:
                if cat in VALID_CATEGORY_FIELDS:
                    qs = qs.filter(**{f'{cat}__gte': CATEGORY_SCORE_THRESHOLD})
                else:
                    logger.warning(f'Unknown category filter: {cat}')

        return qs.order_by('city')


class CityDetailView(generics.RetrieveAPIView):
    """
    GET /api/catalog/cities/<uuid>/
    """
    serializer_class = CitySerializer
    permission_classes = [permissions.IsAuthenticatedOrReadOnly]
    queryset = City.objects.all()


class RecommendedCitiesView(APIView):
    """
    GET /api/catalog/cities/recommended/
    Повертає top-10 міст на основі уподобань юзера (dot-product).
    Якщо preferences порожні — повертає міста з найвищим загальним балом.
    """
    permission_classes = [permissions.IsAuthenticated]

    def get(self, request):
        user_id = request.user.id
        cache_key = f"recommended_cities:{user_id}"
        cached_data = cache.get(cache_key)
        if cached_data is not None:
            return Response(cached_data)

        try:
            preferences = request.user.profile.preferences or []
        except Exception:
            preferences = []

        cities = list(City.objects.all())

        if not preferences:
            scored = sorted(
                cities,
                key=lambda c: sum(
                    getattr(c, field, 0) for field in VALID_CATEGORY_FIELDS
                ),
                reverse=True,
            )
            top_cities = scored[:10]
        else:
            field_weights: dict[str, int] = {}
            for pref in preferences:
                field = PREFERENCE_TO_FIELD.get(pref)
                if field:
                    field_weights[field] = field_weights.get(field, 0) + 1

            if not field_weights:
                top_cities = cities[:10]
            else:
                scored = sorted(
                    cities,
                    key=lambda c: sum(
                        getattr(c, field, 0) * weight
                        for field, weight in field_weights.items()
                    ),
                    reverse=True,
                )
                top_cities = scored[:10]

        serializer = CitySerializer(top_cities, many=True)
        cache.set(cache_key, serializer.data, 3600)  # 1 hour
        return Response(serializer.data)


class ActivityListView(generics.ListAPIView):
    """
    GET /api/catalog/activities/
    Параметри: city (UUID), category
    """
    serializer_class = ActivitySerializer
    permission_classes = [permissions.IsAuthenticatedOrReadOnly]

    def get_queryset(self):
        qs = Activity.objects.select_related('city').all()

        city_id = self.request.query_params.get('city', '').strip()
        if city_id:
            qs = qs.filter(city_id=city_id)

        category = self.request.query_params.get('category', '').strip()
        if category:
            qs = qs.filter(category=category)

        return qs.order_by('title')


class ActivityDetailView(generics.RetrieveAPIView):
    """
    GET /api/catalog/activities/<uuid>/
    """
    serializer_class = ActivitySerializer
    permission_classes = [permissions.IsAuthenticatedOrReadOnly]
    queryset = Activity.objects.select_related('city').all()


class TransportOptionListView(generics.ListAPIView):
    """
    GET /api/catalog/transport/
    Параметри: from, to, type (Flight/Train/Bus), sort_by (base_price / -base_price)
    """
    serializer_class = TransportOptionSerializer
    permission_classes = [permissions.IsAuthenticatedOrReadOnly]

    def list(self, request, *args, **kwargs):
        query_params = tuple(sorted(request.query_params.items()))
        cache_key = f"transport_list:{hash(query_params)}"
        cached_data = cache.get(cache_key)
        if cached_data is not None:
            return Response(cached_data)

        response = super().list(request, *args, **kwargs)
        # кешуємо на 10 хвилин (600 секунд)
        cache.set(cache_key, response.data, 600)
        print(f"REDIS SAVE: saved data for key {cache_key}")
        return response

    def get_queryset(self):
        qs = TransportOption.objects.all()

        from_point = self.request.query_params.get('from', '').strip()
        if from_point:
            qs = qs.filter(departure_point__icontains=from_point)

        to_point = self.request.query_params.get('to', '').strip()
        if to_point:
            qs = qs.filter(arrival_point__icontains=to_point)

        transport_type = self.request.query_params.get('type', '').strip()
        if transport_type:
            qs = qs.filter(transport_type=transport_type)

        sort_by = self.request.query_params.get('sort_by', 'base_price')
        if sort_by in VALID_SORT_TRANSPORT:
            qs = qs.order_by(sort_by)
        else:
            qs = qs.order_by('base_price')

        return qs


class TransportOptionDetailView(generics.RetrieveAPIView):
    """
    GET /api/catalog/transport/<uuid>/
    """
    serializer_class = TransportOptionSerializer
    permission_classes = [permissions.IsAuthenticatedOrReadOnly]
    queryset = TransportOption.objects.all()


class AccommodationOptionListView(generics.ListAPIView):
    """
    GET /api/catalog/accommodations/
    Параметри: city (UUID), min_price, max_price, sort_by (price_per_night / rating)
    """
    serializer_class = AccommodationOptionSerializer
    permission_classes = [permissions.IsAuthenticatedOrReadOnly]

    def list(self, request, *args, **kwargs):
        query_params = tuple(sorted(request.query_params.items()))
        cache_key = f"accommodation_list:{hash(query_params)}"
        cached_data = cache.get(cache_key)
        if cached_data is not None:
            return Response(cached_data)

        response = super().list(request, *args, **kwargs)
        cache.set(cache_key, response.data, 600)  # 10 хвилин
        print(f"REDIS SAVE: saved data for key {cache_key}")

        return response

    def get_queryset(self):
        qs = AccommodationOption.objects.select_related('city').all()

        city_id = self.request.query_params.get('city', '').strip()
        if city_id:
            qs = qs.filter(city_id=city_id)

        min_price = self.request.query_params.get('min_price', '').strip()
        if min_price:
            try:
                qs = qs.filter(price_per_night__gte=float(min_price))
            except ValueError:
                pass

        max_price = self.request.query_params.get('max_price', '').strip()
        if max_price:
            try:
                qs = qs.filter(price_per_night__lte=float(max_price))
            except ValueError:
                pass

        sort_by = self.request.query_params.get('sort_by', 'price_per_night')
        if sort_by in VALID_SORT_ACCOMMODATION:
            qs = qs.order_by(sort_by)
        else:
            qs = qs.order_by('price_per_night')

        return qs


class AccommodationOptionDetailView(generics.RetrieveAPIView):
    """
    GET /api/catalog/accommodations/<uuid>/
    """
    serializer_class = AccommodationOptionSerializer
    permission_classes = [permissions.IsAuthenticatedOrReadOnly]
    queryset = AccommodationOption.objects.select_related('city').all()