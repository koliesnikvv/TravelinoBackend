from rest_framework import serializers
from .models import Trip, TransportBooking, AccommodationBooking, TripActivity


class TripSerializer(serializers.ModelSerializer):
    class Meta:
        model = Trip
        fields = ['id', 'title', 'city', 'start_date', 'end_date', 'owner']
        read_only_fields = ['owner']


class TransportBookingSerializer(serializers.ModelSerializer):
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
    class Meta:
        model = TripActivity
        fields = [
            'id',
            'trip',
            'activity',
            'activity_details_id',
            'scheduled_date',
            'start_time',
            'end_time',
        ]

class TripParticipantSerializer(serializers.ModelSerializer):
    class Meta:
        model = TripParticipant
        fields = ['id', 'trip', 'user', 'invitee_email', 'access_level', 'status']
        read_only_fields = ['status']