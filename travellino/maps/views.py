from django.shortcuts import render

from rest_framework import viewsets, status
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from .models import VisitedCountry
from .serializers import VisitedCountrySerializer


class VisitedCountryViewSet(viewsets.ModelViewSet):
    serializer_class = VisitedCountrySerializer
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        return VisitedCountry.objects.filter(user=self.request.user)

    def perform_create(self, serializer):
        serializer.save(user=self.request.user)
