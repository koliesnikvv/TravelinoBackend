from django.db import models
from django.conf import settings


class VisitedCountry(models.Model):
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='visited_countries'
    )
    country_code = models.CharField(max_length=5)
    country_name = models.CharField(max_length=100)
    visited_at = models.DateField(auto_now_add=True)

    class Meta:
        unique_together = ['user', 'country_code']
        ordering = ['country_name']

    def __str__(self):
        return f"{self.user.email} - {self.country_name}"