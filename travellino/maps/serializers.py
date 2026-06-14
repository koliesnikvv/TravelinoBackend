from rest_framework import serializers
from .models import VisitedCountry

class VisitedCountrySerializer(serializers.ModelSerializer):
    class Meta:
        model = VisitedCountry
        fields = ['id', 'country_code', 'country_name', 'visited_at']
        read_only_fields = ['visited_at']