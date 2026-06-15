"""
Management command: fetch city images from Pexels.

Usage:
    python manage.py fetch_city_images
    python manage.py fetch_city_images --all
    python manage.py fetch_city_images --delay 0.5

Place at: travellino/management/commands/fetch_city_images.py
Requires PEXELS_API_KEY in .env
"""

import time
import logging
import os

import httpx
from django.core.management.base import BaseCommand

from catalog.models import City

logger = logging.getLogger(__name__)

PEXELS_URL = 'https://api.pexels.com/v1/search'


def fetch_image_url(client: httpx.Client, city_name: str, country: str) -> str | None:
    candidates = [
        f'{city_name} city',
        f'{city_name} {country}',
        city_name,
    ]

    for query in candidates:
        try:
            resp = client.get(PEXELS_URL, params={
                'query': query,
                'per_page': 1,
                'orientation': 'landscape',
            })

            if resp.status_code == 429:
                logger.warning('Pexels rate limit — sleeping 60s')
                time.sleep(60)
                continue

            if resp.status_code != 200:
                logger.warning(f'Pexels returned {resp.status_code} for "{query}"')
                continue

            photos = resp.json().get('photos', [])
            if photos:
                # large2x — ~1280px, добре для карточок
                return photos[0]['src']['large2x']

        except Exception as e:
            logger.error(f'Request failed for "{query}": {e}')

    return None


class Command(BaseCommand):
    help = 'Fetch city images from Pexels and save to image_url field'

    def add_arguments(self, parser):
        parser.add_argument('--all', action='store_true',
                            help='Refetch all cities including those that already have an image')
        parser.add_argument('--delay', type=float, default=0.5,
                            help='Seconds between requests (default: 0.5)')

    def handle(self, *args, **options):
        api_key = os.getenv('PEXELS_API_KEY')
        if not api_key:
            self.stderr.write(self.style.ERROR('PEXELS_API_KEY not set in .env'))
            return

        refetch_all = options['all']
        delay = options['delay']

        cities = City.objects.all() if refetch_all else City.objects.filter(image_url='')
        total = cities.count()
        self.stdout.write(f'Processing {total} cities...\n')

        found = 0
        not_found = 0

        headers = {'Authorization': api_key}

        with httpx.Client(timeout=10, headers=headers, follow_redirects=True) as client:
            for i, city in enumerate(cities, start=1):
                self.stdout.write(f'[{i}/{total}] {city.city}, {city.country} ... ', ending='')
                self.stdout.flush()

                image_url = fetch_image_url(client, city.city, city.country)

                if image_url:
                    city.image_url = image_url
                    city.save(update_fields=['image_url'])
                    self.stdout.write(self.style.SUCCESS('OK'))
                    found += 1
                else:
                    self.stdout.write(self.style.WARNING('not found'))
                    not_found += 1

                if i < total:
                    time.sleep(delay)

        self.stdout.write(f'\nDone. Found: {found}, not found: {not_found}\n')