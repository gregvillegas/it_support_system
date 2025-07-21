from django.test import TestCase
from django.contrib.auth.models import User
from django.utils import timezone
from datetime import timedelta
from workorders.models import WorkOrder, TaskType, TaskCategory, UserProfile


class PointsDistributionTestCase(TestCase):
    """Test cases for points distribution system"""
    
    def setUp(self):
        """Set up test data"""
        # Create task type and category
        self.task_type = TaskType.objects.create(
            name="Technical Support", 
            description="Technical support tasks", 
            points_base=100
        )
        self.task_category = TaskCategory.objects.create(
            name="IT Help", 
            description="IT help desk tasks", 
            multiplier=1.5
        )
        
        # Create test users
        self.user1 = User.objects.create_user(username="testuser1")
        self.user2 = User.objects.create_user(username="testuser2")
        self.user3 = User.objects.create_user(username="testuser3")
        self.requester = User.objects.create_user(username="requester")
    
    def test_single_assignee_points_distribution(self):
        """Test points distribution with single assignee"""
        work_order = WorkOrder.objects.create(
            title="Fix printer issue",
            description="Printer not working",
            task_type=self.task_type,
            task_category=self.task_category,
            requester=self.requester,
            priority='medium',
            difficulty_rating=2
        )
        work_order.assigned_to.set([self.user1])
        
        # Change status to resolved
        work_order.status = 'resolved'
        work_order.save()
        
        # Check points calculation (100 * 1.5 * 2 * 1.2 = 360)
        self.assertEqual(work_order.points_earned, 360)
        
        # Check user profile points
        profile1 = UserProfile.objects.get(user=self.user1)
        self.assertEqual(profile1.total_points, 360)
        self.assertEqual(profile1.tickets_resolved, 1)
        self.assertEqual(profile1.level, 1)  # 360 < 1000, so level 1
    
    def test_multiple_assignees_points_distribution(self):
        """Test points distribution with multiple assignees"""
        work_order = WorkOrder.objects.create(
            title="Network troubleshooting",
            description="Network connectivity issues",
            task_type=self.task_type,
            task_category=self.task_category,
            requester=self.requester,
            priority='high',
            difficulty_rating=3
        )
        work_order.assigned_to.set([self.user1, self.user2, self.user3])
        
        # Change status to resolved
        work_order.status = 'resolved'
        work_order.save()
        
        # Check points calculation (100 * 1.5 * 3 * 1.5 = 675)
        self.assertEqual(work_order.points_earned, 675)
        
        # Each user should get 675 // 3 = 225 points
        expected_points_per_user = 225
        
        for user in [self.user1, self.user2, self.user3]:
            profile = UserProfile.objects.get(user=user)
            self.assertEqual(profile.total_points, expected_points_per_user)
            self.assertEqual(profile.tickets_resolved, 1)
    
    def test_time_bonus_points(self):
        """Test time bonus when completed within due date"""
        due_date = timezone.now() + timedelta(days=1)
        
        work_order = WorkOrder.objects.create(
            title="Urgent server maintenance",
            description="Server needs maintenance",
            task_type=self.task_type,
            task_category=self.task_category,
            requester=self.requester,
            priority='urgent',
            difficulty_rating=1,
            due_date=due_date
        )
        work_order.assigned_to.set([self.user1])
        
        # Resolve before due date
        work_order.status = 'resolved'
        work_order.save()
        
        # Check points calculation with time bonus
        # (100 * 1.5 * 1 * 2.0 * 1.5) = 450
        self.assertEqual(work_order.points_earned, 450)
        
        profile1 = UserProfile.objects.get(user=self.user1)
        self.assertEqual(profile1.total_points, 450)
    
    def test_no_points_for_unresolved_tickets(self):
        """Test that no points are awarded for unresolved tickets"""
        work_order = WorkOrder.objects.create(
            title="Pending issue",
            description="Still working on this",
            task_type=self.task_type,
            task_category=self.task_category,
            requester=self.requester,
            status='in_progress'
        )
        work_order.assigned_to.set([self.user1])
        work_order.save()
        
        # No points should be awarded
        self.assertEqual(work_order.points_earned, 0)
        
        # No user profile should be created for unresolved tickets
        self.assertFalse(UserProfile.objects.filter(user=self.user1).exists())
    
    def test_multiple_tickets_same_user(self):
        """Test points accumulation for multiple tickets by same user"""
        # First ticket
        work_order1 = WorkOrder.objects.create(
            title="Fix laptop",
            description="Laptop repair",
            task_type=self.task_type,
            task_category=self.task_category,
            requester=self.requester,
            priority='medium',
            difficulty_rating=2
        )
        work_order1.assigned_to.set([self.user1])
        work_order1.status = 'resolved'
        work_order1.save()
        
        # Second ticket
        work_order2 = WorkOrder.objects.create(
            title="Install software",
            description="Software installation",
            task_type=self.task_type,
            task_category=self.task_category,
            requester=self.requester,
            priority='low',
            difficulty_rating=1
        )
        work_order2.assigned_to.set([self.user1])
        work_order2.status = 'resolved'
        work_order2.save()
        
        # Check accumulated points
        # Ticket 1: 100 * 1.5 * 2 * 1.2 = 360
        # Ticket 2: 100 * 1.5 * 1 * 1.0 = 150
        # Total: 510
        
        profile1 = UserProfile.objects.get(user=self.user1)
        self.assertEqual(profile1.total_points, 510)
        self.assertEqual(profile1.tickets_resolved, 2)
    
    def test_level_calculation(self):
        """Test user level calculation based on points"""
        # Create a high-point ticket to test level progression
        work_order = WorkOrder.objects.create(
            title="Complex system integration",
            description="Large scale system work",
            task_type=self.task_type,
            task_category=self.task_category,
            requester=self.requester,
            priority='urgent',
            difficulty_rating=5
        )
        work_order.assigned_to.set([self.user1])
        work_order.status = 'resolved'
        work_order.save()
        
        # Points: 100 * 1.5 * 5 * 2.0 = 1500 (should be level 2)
        profile1 = UserProfile.objects.get(user=self.user1)
        self.assertEqual(profile1.level, 2)  # 1500 points = level 2
    
    def test_badges_assignment(self):
        """Test badge assignment based on achievements"""
        # Create user profile with high points
        profile = UserProfile.objects.create(
            user=self.user1,
            total_points=1500,
            tickets_resolved=15,
            average_resolution_time=1.5
        )
        
        badges = profile.get_badges()
        
        # Should have multiple badges
        self.assertIn("Bronze Supporter", badges)
        self.assertIn("Problem Solver", badges)
        self.assertIn("Speed Demon", badges)
        
        # Verify badges are saved to profile
        profile.refresh_from_db()
        self.assertEqual(set(profile.badges), set(badges))


class WorkOrderModelTestCase(TestCase):
    """Test cases for WorkOrder model functionality"""
    
    def setUp(self):
        self.task_type = TaskType.objects.create(
            name="Bug Fix", 
            description="Bug fixing tasks", 
            points_base=50
        )
        self.task_category = TaskCategory.objects.create(
            name="Development", 
            description="Development tasks", 
            multiplier=2.0
        )
        self.user = User.objects.create_user(username="developer")
        self.requester = User.objects.create_user(username="client")
    
    def test_ticket_number_generation(self):
        """Test automatic ticket number generation"""
        work_order = WorkOrder.objects.create(
            title="Test ticket",
            description="Test description",
            task_type=self.task_type,
            task_category=self.task_category,
            requester=self.requester
        )
        
        self.assertTrue(work_order.ticket_number.startswith('WO-'))
        self.assertTrue(len(work_order.ticket_number) == 9)  # WO-XXXXXX format
    
    def test_points_calculation_formula(self):
        """Test the points calculation formula"""
        work_order = WorkOrder.objects.create(
            title="Medium priority bug",
            description="Fix critical bug",
            task_type=self.task_type,  # base_points = 50
            task_category=self.task_category,  # multiplier = 2.0
            requester=self.requester,
            priority='medium',  # multiplier = 1.2
            difficulty_rating=3  # multiplier = 3
        )
        
        work_order.status = 'resolved'
        work_order.save()
        
        # Expected: 50 * 2.0 * 3 * 1.0 * 1.2 = 360
        self.assertEqual(work_order.points_earned, 360)
    
    def test_resolved_at_timestamp(self):
        """Test that resolved_at is set when status changes to resolved"""
        work_order = WorkOrder.objects.create(
            title="Test resolution timestamp",
            description="Test description",
            task_type=self.task_type,
            task_category=self.task_category,
            requester=self.requester,
            status='open'
        )
        
        self.assertIsNone(work_order.resolved_at)
        
        work_order.status = 'resolved'
        work_order.save()
        
        self.assertIsNotNone(work_order.resolved_at)
