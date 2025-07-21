from django.core.management.base import BaseCommand
from django.contrib.auth.models import User
from workorders.models import WorkOrder, UserProfile


class Command(BaseCommand):
    help = 'Recalculate all user points from resolved work orders'

    def add_arguments(self, parser):
        parser.add_argument(
            '--dry-run',
            action='store_true',
            help='Show what would be done without making changes',
        )
        parser.add_argument(
            '--reset',
            action='store_true',
            help='Reset all user points before recalculating',
        )

    def handle(self, *args, **options):
        dry_run = options['dry_run']
        reset = options['reset']
        
        if dry_run:
            self.stdout.write(self.style.WARNING('DRY RUN MODE - No changes will be made'))
        
        # Reset points if requested
        if reset:
            if not dry_run:
                UserProfile.objects.all().update(total_points=0, tickets_resolved=0)
                self.stdout.write(self.style.SUCCESS('Reset all user points to 0'))
            else:
                self.stdout.write(self.style.WARNING('Would reset all user points to 0'))
        
        # Get all resolved work orders
        resolved_orders = WorkOrder.objects.filter(
            status='resolved',
            points_earned__gt=0,
            assigned_to__isnull=False
        ).distinct().prefetch_related('assigned_to')
        
        self.stdout.write(f'Found {resolved_orders.count()} resolved work orders with points')
        
        # Track points per user
        user_points = {}
        user_tickets = {}
        
        for order in resolved_orders:
            assignees = list(order.assigned_to.all())
            if not assignees:
                continue
                
            points_per_user = order.points_earned // len(assignees)
            
            self.stdout.write(f'\nWork Order: {order.ticket_number}')
            self.stdout.write(f'  Total Points: {order.points_earned}')
            self.stdout.write(f'  Assignees: {[u.username for u in assignees]} ({len(assignees)} users)')
            self.stdout.write(f'  Points per user: {points_per_user}')
            
            # Track points for each assignee
            for assignee in assignees:
                if assignee.username not in user_points:
                    user_points[assignee.username] = 0
                    user_tickets[assignee.username] = 0
                
                user_points[assignee.username] += points_per_user
                user_tickets[assignee.username] += 1
        
        # Apply the calculated points
        self.stdout.write('\n=== POINT DISTRIBUTION SUMMARY ===')
        for username, total_points in user_points.items():
            try:
                user = User.objects.get(username=username)
                profile, created = UserProfile.objects.get_or_create(user=user)
                
                current_points = profile.total_points
                current_tickets = profile.tickets_resolved
                expected_points = total_points
                expected_tickets = user_tickets[username]
                
                self.stdout.write(f'\n{username}:')
                self.stdout.write(f'  Current: {current_points} points, {current_tickets} tickets')
                self.stdout.write(f'  Expected: {expected_points} points, {expected_tickets} tickets')
                
                if current_points != expected_points or current_tickets != expected_tickets:
                    if not dry_run:
                        if reset:
                            profile.total_points = expected_points
                            profile.tickets_resolved = expected_tickets
                        else:
                            # Only update if different
                            profile.total_points = expected_points
                            profile.tickets_resolved = expected_tickets
                        profile.calculate_level()
                        profile.save()
                        self.stdout.write(
                            self.style.SUCCESS(
                                f'  UPDATED: Set to {expected_points} points, {expected_tickets} tickets'
                            )
                        )
                    else:
                        self.stdout.write(
                            self.style.WARNING(
                                f'  WOULD UPDATE: Set to {expected_points} points, {expected_tickets} tickets'
                            )
                        )
                else:
                    self.stdout.write(
                        self.style.SUCCESS('  ✓ Already correct')
                    )
                    
            except User.DoesNotExist:
                self.stdout.write(
                    self.style.ERROR(f'User {username} not found!')
                )
        
        if dry_run:
            self.stdout.write(
                self.style.WARNING('\nDRY RUN: No changes were made. Use --reset to reset points first, then run without --dry-run to apply changes.')
            )
        else:
            self.stdout.write(
                self.style.SUCCESS('\nPoints recalculation completed!')
            )
