from rest_framework import serializers
from catalog.serializers import ActivitySerializer, TransportOptionSerializer, AccommodationOptionSerializer, CityShortSerializer
from .models import Trip, TransportBooking, AccommodationBooking, TripActivity, TripParticipant


class TripSerializer(serializers.ModelSerializer):
    # city_name as flat string for list view: trip.city_name
    city_name = serializers.CharField(source='city.name', read_only=True)

    class Meta:
        model = Trip
        fields = ['id', 'title', 'city', 'city_name', 'start_date', 'end_date', 'owner']
        read_only_fields = ['owner']


class TransportBookingSerializer(serializers.ModelSerializer):
    # transport_type for display in TransportSection.js: item.transport_type
    transport_type = serializers.CharField(source='transport_option.transport_type', read_only=True)

    class Meta:
        model = TransportBooking
        fields = [
            'id',
            'trip',
            'departure_point',
            'arrival_point',
            'departure_datetime',
            'arrival_datetime',
            'price',
            'passengers_count',
            'transport_option',
            'transport_type',
            'transport_details_id',
        ]


class AccommodationBookingSerializer(serializers.ModelSerializer):
    class Meta:
        model = AccommodationBooking
        fields = [
            'id',
            'trip',
            'accommodation_name',
            'check_in_date',
            'check_out_date',
            'price_per_night',
            'total_price',
            'accommodation_option',
            'accommodation_details_id',
        ]


class TripActivitySerializer(serializers.ModelSerializer):
    # SerializerMethodField instead of source='activity.title' to safely handle activity=None
    # (source='activity.title' would raise AttributeError when activity is None)
    activity_title = serializers.SerializerMethodField()

    def get_activity_title(self, obj):
        return obj.activity.title if obj.activity else 'Custom Activity'

    class Meta:
        model = TripActivity
        fields = [
            'id',
            'trip',
            'activity',
            'activity_title',
            'activity_details_id',
            'scheduled_date',
            'start_time',
            'end_time',
        ]


class TripParticipantSerializer(serializers.ModelSerializer):
    class Meta:
        model = TripParticipant
        fields = ['id', 'trip', 'user', 'invitee_email', 'access_level', 'status']
        # trip is set automatically in perform_create via serializer.save(trip=trip)
        # user is set server-side after the invitee registers
        # status defaults to Pending and is changed via accept_invite action
        read_only_fields = ['trip', 'user', 'status']


class TripDetailSerializer(serializers.ModelSerializer):
    # city as nested object (contains id, name, country) for future use
    city = CityShortSerializer(read_only=True)
    # city_name as flat string for TripHeader.js: trip.city_name
    city_name = serializers.CharField(source='city.city', read_only=True)
    transport = TransportBookingSerializer(source='transport_bookings', many=True, read_only=True)
    accommodation = AccommodationBookingSerializer(source='accommodation_bookings', many=True, read_only=True)
    activities = TripActivitySerializer(many=True, read_only=True)
    participants = TripParticipantSerializer(many=True, read_only=True)
    # current_user_role for TripPage.js: canEdit check
    # returns 'owner', 'edit', or 'view'
    current_user_role = serializers.SerializerMethodField()

    def get_current_user_role(self, obj):
        request = self.context.get('request')
        if not request or not request.user.is_authenticated:
            return 'view'
        if obj.owner == request.user:
            return 'owner'
        participant = obj.participants.filter(
            user=request.user,
            status='Accepted'
        ).first()
        if participant:
            return participant.access_level.lower()  # 'edit' or 'view'
        return 'view'

    class Meta:
        model = Trip
        fields = [
            'id',
            'title',
            'city',
            'city_name',
            'start_date',
            'end_date',
            'owner',
            'transport',
            'accommodation',
            'activities',
            'participants',
            'current_user_role',
        ]


class TransportBookingDetailSerializer(serializers.ModelSerializer):
    transport_option = TransportOptionSerializer(read_only=True)

    class Meta:
        model = TransportBooking
        fields = [
            'id',
            'departure_point',
            'arrival_point',
            'departure_datetime',
            'arrival_datetime',
            'price',
            'passengers_count',
            'transport_option',
            'transport_details_id',
        ]


class AccommodationBookingDetailSerializer(serializers.ModelSerializer):
    accommodation_option = AccommodationOptionSerializer(read_only=True)

    class Meta:
        model = AccommodationBooking
        fields = [
            'id',
            'accommodation_name',
            'check_in_date',
            'check_out_date',
            'price_per_night',
            'total_price',
            'accommodation_option',
            'accommodation_details_id',
        ]


class TripActivityDetailSerializer(serializers.ModelSerializer):
    activity = ActivitySerializer(read_only=True)
    # SerializerMethodField instead of source='activity.title' to safely handle activity=None
    activity_title = serializers.SerializerMethodField()

    def get_activity_title(self, obj):
        return obj.activity.title if obj.activity else 'Custom Activity'

    class Meta:
        model = TripActivity
        fields = [
            'id',
            'activity',
            'activity_title',
            'activity_details_id',
            'scheduled_date',
            'start_time',
            'end_time',
        ]