import logging

from django.core.cache import cache
from django.db.models import Q
from rest_framework import generics, permissions, status
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
from .services import (
    CATEGORY_TO_KINDS,
    get_city_coordinates,
    get_place_detail,
    search_places,
    build_place_detail_response,
)

logger = logging.getLogger(__name__)

CATEGORY_SCORE_THRESHOLD = 5

VALID_CATEGORY_FIELDS = [
    'culture', 'adventure', 'nature', 'beaches',
    'nightlife', 'cuisine', 'wellness', 'urban', 'seclusion',
]

PREFERENCE_TO_FIELD = {
    'museums':      'culture',
    'architecture': 'culture',
    'history':      'culture',
    'photography':  'culture',
    'beaches':      'beaches',
    'surfing':      'beaches',
    'beach':        'beaches',
    'seafood':      'cuisine',
    'coffee':       'cuisine',
    'street-food':  'cuisine',
    'hiking':       'nature',
    'mountains':    'nature',
    'nature':       'nature',
    'shopping':     'urban',
    'city':         'urban',
    'nightlife':    'nightlife',
    'wellness':     'wellness',
    'asia':         'adventure',
}

VALID_SORT_TRANSPORT = ['base_price', '-base_price']
VALID_SORT_ACCOMMODATION = ['price_per_night', '-price_per_night', 'rating', '-rating']

VALID_RATE_VALUES = {'1', '2', '3', '1h', '2h', '3h'}
VALID_PRICE_VALUES = {'budget', 'moderate', 'expensive'}
VALID_LOCATION_TYPE_VALUES = {'outdoor', 'indoor'}
VALID_VIBE_VALUES = {'active', 'relaxed'}


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
    """
    permission_classes = [permissions.IsAuthenticated]

    def get(self, request):
        user_id = request.user.id
        cache_key = f'recommended_cities:{user_id}'
        cached = cache.get(cache_key)
        if cached is not None:
            return Response(cached)

        try:
            preferences = request.user.profile.preferences or []
        except Exception:
            preferences = []

        cities = list(City.objects.all())

        if not preferences:
            scored = sorted(
                cities,
                key=lambda c: sum(getattr(c, f, 0) for f in VALID_CATEGORY_FIELDS),
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
        cache.set(cache_key, serializer.data, 3600)
        return Response(serializer.data)


class ActivityListView(APIView):
    """
    GET /api/catalog/activities/
    Params:
        city            UUID, required
        query           free text
        category        Culture | Adventure | Nature | Beaches | Nightlife | Cuisine | Wellness | Urban | Seclusion
        rate            1 | 2 | 3
        price           budget | moderate | expensive
        location_type   outdoor | indoor
        vibe            active | relaxed
        page            int, default 1, returns 10 results per page
    """
    permission_classes = [permissions.IsAuthenticatedOrReadOnly]

    def get(self, request):
        city_id = request.query_params.get('city', '').strip()
        query = request.query_params.get('query', '').strip()
        category = request.query_params.get('category', '').strip()
        rate = request.query_params.get('rate', '').strip()
        price = request.query_params.get('price', '').strip()
        location_type = request.query_params.get('location_type', '').strip()
        vibe = request.query_params.get('vibe', '').strip()

        try:
            page = max(1, int(request.query_params.get('page', 1)))
        except ValueError:
            page = 1

        if not city_id:
            return Response({'error': 'city parameter is required'}, status=status.HTTP_400_BAD_REQUEST)

        if rate and rate not in VALID_RATE_VALUES:
            return Response(
                {'error': f'Invalid rate. Valid values: {", ".join(VALID_RATE_VALUES)}'},
                status=status.HTTP_400_BAD_REQUEST
            )

        try:
            city = City.objects.get(pk=city_id)
        except City.DoesNotExist:
            return Response({'error': 'City not found'}, status=status.HTTP_404_NOT_FOUND)

        # cache key covers all search params — same params = same cached result
        search_params_hash = hash((city_id, query, category, rate, price, location_type, vibe))
        cache_key = f'activity_search:{city_id}:{search_params_hash}'

        full_results = cache.get(cache_key)
        if full_results is None:
            coords = get_city_coordinates(city.city)
            if not coords:
                return Response({'error': 'Failed to get city coordinates'}, status=status.HTTP_502_BAD_GATEWAY)

            lat, lon = coords
            full_results = search_places(
                lat=lat,
                lon=lon,
                query=query,
                category=category,
                rate=rate,
                price=price,
                location_type=location_type,
                vibe=vibe,
            )
            # cache full ranked list for 1 hour
            cache.set(cache_key, full_results, 3600)

        page_size = 10
        start = (page - 1) * page_size
        end = start + page_size
        page_results = full_results[start:end]

        return Response({
            'results': page_results,
            'page': page,
            'total': len(full_results),
            'has_next': end < len(full_results),
        })


class ActivityDetailView(APIView):
    """
    GET /api/catalog/activities/<xid>/
    Returns: { xid, name, description, kinds, image, address, otm_url }
    """
    permission_classes = [permissions.IsAuthenticatedOrReadOnly]

    def get(self, request, pk=None):
        xid = pk
        cache_key = f'place_detail:{xid}'
        cached = cache.get(cache_key)
        if cached:
            return Response(cached)

        data = get_place_detail(xid)
        if data is None:
            return Response({'error': 'Failed to fetch place details'}, status=status.HTTP_502_BAD_GATEWAY)

        result = build_place_detail_response(xid, data)
        cache.set(cache_key, result, 3600)
        return Response(result)


class TransportOptionListView(generics.ListAPIView):
    """
    GET /api/catalog/transport/
    """
    serializer_class = TransportOptionSerializer
    permission_classes = [permissions.IsAuthenticatedOrReadOnly]

    def list(self, request, *args, **kwargs):
        query_params = tuple(sorted(request.query_params.items()))
        cache_key = f'transport_list:{hash(query_params)}'
        cached = cache.get(cache_key)
        if cached is not None:
            return Response(cached)

        response = super().list(request, *args, **kwargs)
        cache.set(cache_key, response.data, 600)
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
    """
    serializer_class = AccommodationOptionSerializer
    permission_classes = [permissions.IsAuthenticatedOrReadOnly]

    def list(self, request, *args, **kwargs):
        query_params = tuple(sorted(request.query_params.items()))
        cache_key = f'accommodation_list:{hash(query_params)}'
        cached = cache.get(cache_key)
        if cached is not None:
            return Response(cached)

        response = super().list(request, *args, **kwargs)
        cache.set(cache_key, response.data, 600)
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