import uuid
import pandas as pd
from django.core.management.base import BaseCommand, CommandError
from catalog.models import City

#to run enter python manage.py import_cities data/cities_dataset.csv

class Command(BaseCommand):
    help = 'Imports city data from a CSV dataset into the database'

    def add_arguments(self, parser):
        parser.add_argument('file_path', type=str, help='Path to the CSV dataset file')

    def handle(self, *args, **options):
        file_path = options['file_path']

        if not file_path.endswith('.csv'):
            raise CommandError("Invalid file format. This commands only supports .csv files.")

        self.stdout.write(self.style.NOTICE(f"Reading CSV file: {file_path}..."))

        try:
            df = pd.read_csv(file_path)
        except Exception as e:
            raise CommandError(f"Failed to read CSV file: {e}")

        self.stdout.write(self.style.NOTICE(f"Rows found for import: {len(df)}"))

        created_count = 0
        updated_count = 0

        for index, row in df.iterrows():
            try:
                # Handle UUID
                row_id = row.get('id')
                city_id = uuid.UUID(str(row_id)) if row_id else uuid.uuid4()

                ideal_durations = row.get('ideal_durations', [])
                if isinstance(ideal_durations, str):
                    clean_str = ideal_durations.strip("[]\"' ")
                    ideal_durations = [x.strip("['\" ]") for x in clean_str.split(',') if x.strip()]

                city_data = {
                    'city': row['city'],
                    'country': row['country'],
                    'region': row['region'],
                    'short_description': row['short_description'],
                    'ideal_durations': ideal_durations,
                    'budget_level': row['budget_level'],

                    # Direct cast to int since dataset guarantees no null values
                    'culture': int(row['culture']),
                    'adventure': int(row['adventure']),
                    'nature': int(row['nature']),
                    'beaches': int(row['beaches']),
                    'nightlife': int(row['nightlife']),
                    'cuisine': int(row['cuisine']),
                    'wellness': int(row['wellness']),
                    'urban': int(row['urban']),
                    'seclusion': int(row['seclusion']),

                    # Optional fields (uncomment if activated in models.py)
                    # 'latitude': float(row['latitude']),
                    # 'longitude': float(row['longitude']),
                }

                # Using update_or_create to allow safe re-runs without duplication
                obj, created = City.objects.update_or_create(
                    id=city_id,
                    defaults=city_data
                )

                if created:
                    created_count += 1
                else:
                    updated_count += 1

            except Exception as e:
                self.stdout.write(self.style.ERROR(f"Error at row {index} ({row.get('city')}): {e}"))
                continue

        self.stdout.write(self.style.SUCCESS(
            f"Import completed! Created: {created_count}, Updated: {updated_count}."
        ))