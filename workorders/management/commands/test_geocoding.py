from django.core.management.base import BaseCommand
from django.contrib.auth.models import User
from django.test import RequestFactory
from workorders.views import geocode_location


class Command(BaseCommand):
    help = 'Test geocoding functionality'

    def add_arguments(self, parser):
        parser.add_argument(
            'location',
            type=str,
            help='Location to geocode',
        )

    def handle(self, *args, **options):
        location = options['location']
        
        # Create a test user and request
        user = User.objects.filter(is_staff=True).first()
        if not user:
            self.stdout.write(self.style.ERROR('No staff user found for testing'))
            return
        
        # Create a mock request
        factory = RequestFactory()
        request = factory.post('/geocode/', {'location_name': location})
        request.user = user
        
        # Call the geocode function
        response = geocode_location(request)
        
        # Parse and display the response
        if hasattr(response, 'content'):
            import json
            try:
                data = json.loads(response.content)
                if data.get('success'):
                    self.stdout.write(
                        self.style.SUCCESS(
                            f'Successfully found location: {data.get("display_name")}'
                        )
                    )
                    self.stdout.write(f'Latitude: {data.get("latitude")}')
                    self.stdout.write(f'Longitude: {data.get("longitude")}')
                else:
                    self.stdout.write(
                        self.style.ERROR(f'Geocoding failed: {data.get("error")}')
                    )
            except json.JSONDecodeError:
                self.stdout.write(
                    self.style.ERROR(f'Invalid JSON response: {response.content}')
                )
        else:
            self.stdout.write(self.style.ERROR('No response content'))
