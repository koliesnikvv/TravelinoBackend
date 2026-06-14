from django.db.models.signals import post_save, post_delete
from django.dispatch import receiver
from django.core.cache import cache
from .models import TransportOption, AccommodationOption

@receiver([post_save, post_delete], sender=TransportOption)
def clear_transport_cache(sender, **kwargs):
    # Очищаємо всі ключі кешу транспорту
    cache.delete_pattern("transport_list:*")


@receiver([post_save, post_delete], sender=AccommodationOption)
def clear_accommodation_cache(sender, **kwargs):
    cache.delete_pattern("accommodation_list:*")