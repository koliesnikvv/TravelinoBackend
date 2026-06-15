from rest_framework import serializers
from catalog.serializers import ActivitySerializer, TransportOptionSerializer, AccommodationOptionSerializer, CityShortSerializer
from .models import Trip, TransportBooking, AccommodationBooking, TripActivity, TripParticipant


class TripSerializer(serializers.ModelSerializer):
    city_name = serializers.CharField(source='city.city', read_only=True)

    class Meta:
        model = Trip
        fields = ['id', 'title', 'city', 'city_name', 'start_date', 'end_date', 'owner']
        read_only_fields = ['owner']


class TransportBookingSerializer(serializers.ModelSerializer):
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
        read_only_fields = ['id', 'trip']


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
        read_only_fields = ['id', 'trip']


class TripActivitySerializer(serializers.ModelSerializer):
    # Priority: activity.title (catalog FK) > activity_name (saved from OTM) > fallback
    activity_title = serializers.SerializerMethodField()

    def get_activity_title(self, obj):
        if obj.activity:
            return obj.activity.title
        if obj.activity_name:
            return obj.activity_name
        return 'Activity'

    class Meta:
        model = TripActivity
        fields = [
            'id',
            'trip',
            'activity',
            'activity_title',
            'activity_name',
            'activity_details_id',
            'scheduled_date',
            'start_time',
            'end_time',
        ]
        read_only_fields = ['id', 'trip']


class TripParticipantSerializer(serializers.ModelSerializer):
    class Meta:
        model = TripParticipant
        fields = ['id', 'trip', 'user', 'invitee_email', 'access_level', 'status']
        read_only_fields = ['trip', 'user', 'status']


class TripDetailSerializer(serializers.ModelSerializer):
    city = CityShortSerializer(read_only=True)
    city_name = serializers.CharField(source='city.city', read_only=True)
    transport = TransportBookingSerializer(source='transport_bookings', many=True, read_only=True)
    accommodation = AccommodationBookingSerializer(source='accommodation_bookings', many=True, read_only=True)
    activities = TripActivitySerializer(many=True, read_only=True)
    participants = TripParticipantSerializer(many=True, read_only=True)
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
            return participant.access_level.lower()
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
    activity_title = serializers.SerializerMethodField()

    def get_activity_title(self, obj):
        if obj.activity:
            return obj.activity.title
        if obj.activity_name:
            return obj.activity_name
        return 'Activity'

    class Meta:
        model = TripActivity
        fields = [
            'id',
            'activity',
            'activity_title',
            'activity_name',
            'activity_details_id',
            'scheduled_date',
            'start_time',
            'end_time',
        ]