import csv
import json
import os

from django.core.management.base import BaseCommand, CommandError

from catalog.models import City

# rewrite
#python manage.py import_cities data/cities_dataset.csv
# upsert
#python manage.py import_cities data/cities_dataset.csv --no-clear

class Command(BaseCommand):
    help = 'Import cities from CSV dataset. Clears existing cities and re-imports from scratch.'

    def add_arguments(self, parser):
        parser.add_argument(
            'csv_path',
            type=str,
            help='Absolute or relative path to the cities CSV file.',
        )
        parser.add_argument(
            '--no-clear',
            action='store_true',
            help='Skip clearing existing cities before import (upsert by id instead).',
        )

    def handle(self, *args, **options):
        csv_path = options['csv_path']

        if not os.path.exists(csv_path):
            raise CommandError(f'File not found: {csv_path}')

        no_clear = options['no_clear']

        if not no_clear:
            deleted_count, _ = City.objects.all().delete()
            self.stdout.write(f'Cleared {deleted_count} existing cities.')

        created = 0
        updated = 0
        errors = 0

        with open(csv_path, newline='', encoding='utf-8') as f:
            reader = csv.DictReader(f)

            for i, row in enumerate(reader, start=1):
                try:
                    # ideal_durations is stored as JSON array string: ["Short trip","One week"]
                    ideal_durations = json.loads(row['ideal_durations'])

                    city_data = dict(
                        city=row['city'].strip(),
                        country=row['country'].strip(),
                        region=row['region'].strip(),
                        short_description=row['short_description'].strip(),
                        ideal_durations=ideal_durations,
                        budget_level=row['budget_level'].strip(),
                        culture=int(row['culture']),
                        adventure=int(row['adventure']),
                        nature=int(row['nature']),
                        beaches=int(row['beaches']),
                        nightlife=int(row['nightlife']),
                        cuisine=int(row['cuisine']),
                        wellness=int(row['wellness']),
                        urban=int(row['urban']),
                        seclusion=int(row['seclusion']),
                        # reserve fields — uncomment when models are migrated
                        # latitude=row['latitude'],
                        # longitude=row['longitude'],
                        # avg_temp_monthly=json.loads(row['avg_temp_monthly']),
                    )

                    if no_clear:
                        _, was_created = City.objects.update_or_create(
                            id=row['id'].strip(),
                            defaults=city_data,
                        )
                        if was_created:
                            created += 1
                        else:
                            updated += 1
                    else:
                        City.objects.create(id=row['id'].strip(), **city_data)
                        created += 1

                except Exception as e:
                    errors += 1
                    self.stderr.write(f'Row {i} ({row.get("city", "?")}): {e}')

        self.stdout.write(self.style.SUCCESS(
            f'Done. Created: {created}, Updated: {updated}, Errors: {errors}.'
        ))
