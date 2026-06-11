from django.db.models import Q
from rest_framework import viewsets, status
from rest_framework.decorators import action
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from amadeus import Client, ResponseError, Location
from django.conf import settings
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import AllowAny
from .flights import Flight

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

from django.views.decorators.csrf import csrf_exempt
from django.http import JsonResponse
import json
# Додайте цю функцію в views.py
from django.http import JsonResponse
from amadeus import ResponseError


def test_amadeus(request):
    term = request.GET.get('term', 'London')

    try:
        response = amadeus.reference_data.locations.get(
            keyword=term,
            subType=Location.CITY
        )

        results = []
        for item in response.data[:5]:
            results.append({
                'name': item.get('name'),
                'iataCode': item.get('iataCode'),
                'country': item.get('address', {}).get('countryCode')
            })

        return JsonResponse({
            'success': True,
            'count': len(results),
            'results': results
        })

    except ResponseError as e:
        return JsonResponse({
            'success': False,
            'error': str(e),
            'response_body': e.response.body if hasattr(e, 'response') else None
        }, status=400)
    except Exception as e:
        return JsonResponse({
            'success': False,
            'error': str(e)
        }, status=400)

amadeus = Client(
    client_id=settings.AMADEUS_API_KEY,
    client_secret=settings.AMADEUS_API_SECRET
)

def get_flight_offers(**kwargs):
    try:
        search_flights = amadeus.shopping.flight_offers_search.get(**kwargs)
        flight_offers = []

        for flight in search_flights.data:
            offer = Flight(flight).construct_flights()

            try:
                first_segment = flight["itineraries"][0]["segments"][0]
                last_segment = flight["itineraries"][0]["segments"][-1]

                airline = first_segment["carrierCode"]
                origin_code = first_segment["departure"]["iataCode"]
                destination_code = last_segment["arrival"]["iataCode"]
                date = first_segment["departure"]["at"].split("T")[0]

                offer["bookingLink"] = generate_booking_link(
                    airline,
                    origin_code,
                    destination_code,
                    date
                )
            except Exception as e:
                print(f"Could not generate booking link: {e}")
                offer["bookingLink"] = None

            flight_offers.append(offer)

        return flight_offers
    except ResponseError as e:
        print(f"Amadeus API error: {e}")
        return []


def generate_booking_link(airline, origin, destination, date):
    AIRLINE_LINKS = {
        "IB": "https://www.iberia.com/flights/?origin={o}&destination={d}&departureDate={date}",
        "LH": "https://www.lufthansa.com/fl/en/flight-search?origin={o}&destination={d}&departureDate={date}",
        "KL": "https://www.klm.com/travel/ua_en/plan_and_book/book_a_flight/index.htm?origin={o}&destination={d}&departureDate={date}",
        "AF": "https://wwws.airfrance.com.ua/search?origin={o}&destination={d}&outboundDate={date}",
        "BA": "https://www.britishairways.com/travel/home/public/en_ua",
        "UA": "https://www.united.com/",
        "DL": "https://www.delta.com/",
    }

    if airline in AIRLINE_LINKS:
        return AIRLINE_LINKS[airline].format(
            o=origin,
            d=destination,
            date=date
        )
    return f"https://www.kayak.com/flights/{origin}-{destination}/{date}"


def build_price_metrics(flight_offers):
    if not flight_offers:
        return {"min": 0, "max": 0, "cheapest_flight": 0}

    prices = [float(f["price"]) for f in flight_offers if f.get("price")]
    if not prices:
        return {"min": 0, "max": 0, "cheapest_flight": 0}

    prices.sort()
    return {
        "min": prices[0],
        "max": prices[-1],
        "cheapest_flight": prices[0],
    }


@csrf_exempt
def flight_offers(request):
    if request.method != "POST":
        return JsonResponse({"error": "POST required"}, status=405)

    try:
        data = json.loads(request.body)
        print("=" * 50)
        print("FLIGHT SEARCH REQUEST:")
        print(f"Full data: {data}")

        origin = data.get('origin') or data.get('Origin')
        destination = data.get('destination') or data.get('Destination')
        departure_date = data.get('departureDate') or data.get('Departuredate')
        return_date = data.get('returnDate') or data.get('Returndate')
        adults = data.get('adults', 1)

        print(f"Origin: {origin}")
        print(f"Destination: {destination}")
        print(f"Departure date: {departure_date}")
        print(f"Return date: {return_date}")
        print(f"Adults: {adults}")
        print("=" * 50)

    except json.JSONDecodeError as e:
        return JsonResponse({"error": f"Invalid JSON: {str(e)}"}, status=400)


    if not origin or not destination or not departure_date:
        return JsonResponse({"error": "Missing required parameters: origin, destination, departureDate"}, status=400)

    kwargs = {
        'originLocationCode': origin.upper(),
        'destinationLocationCode': destination.upper(),
        'departureDate': departure_date,
        'adults': int(adults)
    }

    if return_date:
        kwargs['returnDate'] = return_date

    try:
        flight_offers_data = get_flight_offers(**kwargs)
        metrics = build_price_metrics(flight_offers_data)

        response_data = {
            'flight_offers': flight_offers_data,
            'metrics': metrics
        }

        print(f"Found {len(flight_offers_data)} flights")
        return JsonResponse(response_data)

    except ResponseError as e:
        print(f"Amadeus API error: {e}")
        return JsonResponse({'error': str(e)}, status=400)
    except Exception as e:
        print(f"Unexpected error: {e}")
        return JsonResponse({'error': str(e)}, status=400)


@csrf_exempt
def hotel_search(request):
    if request.method != "POST":
        return JsonResponse({"error": "POST required"}, status=405)

    try:
        data = json.loads(request.body)
    except json.JSONDecodeError:
        return JsonResponse({"error": "Invalid JSON"}, status=400)

    city_code = data.get("cityCode")
    check_in = data.get("checkInDate")
    check_out = data.get("checkOutDate")
    adults = data.get("adults", 1)

    if not city_code or not check_in or not check_out:
        return JsonResponse({"error": "Missing required parameters"}, status=400)

    try:
        hotels = amadeus.reference_data.locations.hotels.by_city.get(
            cityCode=city_code
        ).data

        hotel_ids = [h["hotelId"] for h in hotels[:20]]

        offers = amadeus.shopping.hotel_offers_search.get(
            hotelIds=hotel_ids,
            checkInDate=check_in,
            checkOutDate=check_out,
            adults=adults
        ).data

        results = []
        prices = []

        for hotel_data in offers:
            hotel = hotel_data["hotel"]
            for offer in hotel_data["offers"]:
                price = float(offer["price"]["total"])
                prices.append(price)

                results.append({
                    "hotelId": hotel["hotelId"],
                    "name": hotel["name"],
                    "cityCode": hotel.get("cityCode", city_code),
                    "price": price,
                    "currency": offer["price"]["currency"],
                    "offerId": offer["id"],
                    "bookingLink": f"https://www.booking.com/searchresults.html?ss={hotel['name']}"
                })

        metrics = {
            "min": min(prices) if prices else 0,
            "max": max(prices) if prices else 0,
            "cheapest": prices[0] if prices else 0
        }

        return JsonResponse({
            "hotels": results,
            "metrics": metrics
        })

    except ResponseError as e:
        return JsonResponse({"error": str(e)}, status=400)


def airport_search(request):
    term = request.GET.get('term', '')
    if not term or len(term) < 2:
        return JsonResponse([], safe=False)

    try:
        response = amadeus.reference_data.locations.get(
            keyword=term,
            subType=Location.ANY
        ).data

        results = []
        for item in response[:10]:
            city_name = item.get('address', {}).get('cityName', '')
            results.append({
                "name": item.get('name'),
                "iataCode": item.get('iataCode'),
                "type": item.get('subType'),
                "city": city_name
            })
        return JsonResponse(results, safe=False)
    except ResponseError as e:
        return JsonResponse([], safe=False)


@api_view(['GET'])
@permission_classes([AllowAny])


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