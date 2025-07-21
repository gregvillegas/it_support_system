from django.core.management.base import BaseCommand
from django.contrib.auth.models import User
from workorders.models import WorkOrder, UserProfile


class Command(BaseCommand):
    help = 'Award missing points for resolved work orders'

    def add_arguments(self, parser):
        parser.add_argument(
            '--dry-run',
            action='store_true',
            help='Show what would be done without making changes',
        )

    def handle(self, *args, **options):
        dry_run = options['dry_run']
        
        if dry_run:
            self.stdout.write(self.style.WARNING('DRY RUN MODE - No changes will be made'))
        
        # Get all resolved work orders with points but potentially missing user points
        resolved_orders = WorkOrder.objects.filter(
            status='resolved',
            points_earned__gt=0,
            assigned_to__isnull=False
        )
        
        self.stdout.write(f'Found {resolved_orders.count()} resolved work orders with points')
        
        fixed_count = 0
        
        for order in resolved_orders:
            assignees = order.assigned_to.all()
            if not assignees:
                continue
                
            points_per_user = order.points_earned // len(assignees)
            
            self.stdout.write(f'\nWork Order: {order.ticket_number}')
            self.stdout.write(f'  Points: {order.points_earned}')
            self.stdout.write(f'  Assignees: {[u.username for u in assignees]}')
            self.stdout.write(f'  Points per user: {points_per_user}')
            
            # Check if points were already awarded by looking at profiles
            needs_points = []
            for assignee in assignees:
                profile, created = UserProfile.objects.get_or_create(user=assignee)
                
                # This is a simplified check - in a real scenario you might want
                # to track which tickets contributed to the points
                if created or profile.total_points == 0:
                    needs_points.append((assignee, profile))
            
            if needs_points:
                self.stdout.write(f'  Users needing points: {[u.username for u, p in needs_points]}')
                
                if not dry_run:
                    for assignee, profile in needs_points:
                        profile.add_points(points_per_user)
                        profile.tickets_resolved += 1
                        profile.save()
                        self.stdout.write(
                            self.style.SUCCESS(
                                f'    Awarded {points_per_user} points to {assignee.username}'
                            )
                        )
                    fixed_count += 1
                else:
                    self.stdout.write(
                        self.style.WARNING(
                            f'    Would award {points_per_user} points to each user (DRY RUN)'
                        )
                    )
            else:
                self.stdout.write('  All users already have points')
        
        if dry_run:
            self.stdout.write(
                self.style.WARNING(f'\nDRY RUN: Would have fixed {fixed_count} work orders')
            )
        else:
            self.stdout.write(
                self.style.SUCCESS(f'\nFixed {fixed_count} work orders')
            )
