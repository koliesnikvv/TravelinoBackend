from django.db.models.signals import post_save
from django.dispatch import receiver
from django.core.cache import cache
from .models import UserProfile

@receiver(post_save, sender=UserProfile)
def clear_recommendations_cache(sender, instance, **kwargs):
    cache_key = f"recommended_cities:{instance.user_id}"
    cache.delete(cache_key)