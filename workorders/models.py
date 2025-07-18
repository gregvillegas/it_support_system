from django.db import models
from django.contrib.auth.models import User
from django.core.validators import MinValueValidator, MaxValueValidator
from django.core.exceptions import ValidationError
from django.utils import timezone
from email_validator import validate_email, EmailNotValidError


class TaskType(models.Model):
    name = models.CharField(max_length=100, unique=True)
    description = models.TextField(blank=True)
    points_base = models.IntegerField(default=10, help_text="Base points for this task type")
    created_at = models.DateTimeField(auto_now_add=True)
    
    def __str__(self):
        return self.name
    
    class Meta:
        ordering = ['name']


class TaskCategory(models.Model):
    name = models.CharField(max_length=100, unique=True)
    description = models.TextField(blank=True)
    color = models.CharField(max_length=7, default='#007bff', help_text="Hex color code for category")
    multiplier = models.FloatField(default=1.0, help_text="Points multiplier for this category")
    created_at = models.DateTimeField(auto_now_add=True)
    
    def __str__(self):
        return self.name
    
    class Meta:
        ordering = ['name']
        verbose_name_plural = "Task Categories"


class WorkOrder(models.Model):
    PRIORITY_CHOICES = [
        ('low', 'Low'),
        ('medium', 'Medium'),
        ('high', 'High'),
        ('urgent', 'Urgent'),
    ]
    
    STATUS_CHOICES = [
        ('open', 'Open'),
        ('in_progress', 'In Progress'),
        ('waiting', 'Waiting for Customer'),
        ('resolved', 'Resolved'),
        ('closed', 'Closed'),
    ]
    
    # Basic Information
    ticket_number = models.CharField(max_length=20, unique=True, editable=False)
    title = models.CharField(max_length=200)
    description = models.TextField()
    
    # Task Classification
    task_type = models.ForeignKey(TaskType, on_delete=models.CASCADE)
    task_category = models.ForeignKey(TaskCategory, on_delete=models.CASCADE)
    
    # Priority and Status
    priority = models.CharField(max_length=10, choices=PRIORITY_CHOICES, default='medium')
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='open')
    
    # People
    requester = models.ForeignKey(User, on_delete=models.CASCADE, related_name='requested_tickets')
    assigned_to = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True, related_name='assigned_tickets')
    
    # Location
    location_name = models.CharField(max_length=200, blank=True)
    latitude = models.FloatField(null=True, blank=True)
    longitude = models.FloatField(null=True, blank=True)
    
    # Time Tracking
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    due_date = models.DateTimeField(null=True, blank=True)
    resolved_at = models.DateTimeField(null=True, blank=True)
    
    # Gamification
    points_earned = models.IntegerField(default=0, editable=False)
    difficulty_rating = models.IntegerField(
        default=1,
        validators=[MinValueValidator(1), MaxValueValidator(5)],
        help_text="Difficulty rating from 1-5"
    )
    
    def save(self, *args, **kwargs):
        if not self.ticket_number:
            # Generate ticket number
            count = WorkOrder.objects.count() + 1
            self.ticket_number = f"WO-{count:06d}"
        
        # Calculate points when resolved
        if self.status == 'resolved' and not self.resolved_at:
            self.resolved_at = timezone.now()
            self.calculate_points()
        
        super().save(*args, **kwargs)
    
    def calculate_points(self):
        """Calculate points based on task type, category, difficulty, and time to resolution"""
        base_points = self.task_type.points_base
        category_multiplier = self.task_category.multiplier
        difficulty_multiplier = self.difficulty_rating
        
        # Time bonus (completed within due date)
        time_bonus = 1.0
        if self.due_date and self.resolved_at and self.resolved_at <= self.due_date:
            time_bonus = 1.5
        
        # Priority multiplier
        priority_multipliers = {
            'low': 1.0,
            'medium': 1.2,
            'high': 1.5,
            'urgent': 2.0
        }
        priority_multiplier = priority_multipliers.get(self.priority, 1.0)
        
        self.points_earned = int(
            base_points * 
            category_multiplier * 
            difficulty_multiplier * 
            time_bonus * 
            priority_multiplier
        )
    
    def __str__(self):
        return f"{self.ticket_number} - {self.title}"
    
    class Meta:
        ordering = ['-created_at']


class WorkOrderComment(models.Model):
    work_order = models.ForeignKey(WorkOrder, on_delete=models.CASCADE, related_name='comments')
    author = models.ForeignKey(User, on_delete=models.CASCADE)
    comment = models.TextField()
    created_at = models.DateTimeField(auto_now_add=True)
    
    def __str__(self):
        return f"Comment by {self.author} on {self.work_order}"
    
    class Meta:
        ordering = ['-created_at']


class UserProfile(models.Model):
    user = models.OneToOneField(User, on_delete=models.CASCADE)
    total_points = models.IntegerField(default=0)
    level = models.IntegerField(default=1)
    badges = models.JSONField(default=list, blank=True)
    tickets_resolved = models.IntegerField(default=0)
    average_resolution_time = models.FloatField(default=0.0, help_text="Average resolution time in hours")
    
    def calculate_level(self):
        """Calculate user level based on total points"""
        # Level up every 1000 points
        self.level = max(1, self.total_points // 1000 + 1)
        return self.level
    
    def add_points(self, points):
        """Add points and update level"""
        self.total_points += points
        self.calculate_level()
        self.save()
    
    def get_badges(self):
        """Get user badges based on achievements"""
        badges = []
        
        # Points-based badges
        if self.total_points >= 1000:
            badges.append("Bronze Supporter")
        if self.total_points >= 5000:
            badges.append("Silver Supporter")
        if self.total_points >= 10000:
            badges.append("Gold Supporter")
        if self.total_points >= 25000:
            badges.append("Platinum Supporter")
        
        # Resolution-based badges
        if self.tickets_resolved >= 10:
            badges.append("Problem Solver")
        if self.tickets_resolved >= 50:
            badges.append("Expert Resolver")
        if self.tickets_resolved >= 100:
            badges.append("Master Technician")
        
        # Speed-based badges
        if self.average_resolution_time > 0 and self.average_resolution_time <= 2:
            badges.append("Speed Demon")
        if self.average_resolution_time > 0 and self.average_resolution_time <= 1:
            badges.append("Lightning Fast")
        
        self.badges = badges
        self.save()
        return badges
    
    def __str__(self):
        return f"{self.user.username} - Level {self.level} ({self.total_points} points)"


class KPIReport(models.Model):
    REPORT_TYPES = [
        ('daily', 'Daily'),
        ('weekly', 'Weekly'),
        ('monthly', 'Monthly'),
        ('yearly', 'Yearly'),
    ]
    
    report_type = models.CharField(max_length=10, choices=REPORT_TYPES)
    date_from = models.DateField()
    date_to = models.DateField()
    
    # Metrics
    total_tickets = models.IntegerField(default=0)
    resolved_tickets = models.IntegerField(default=0)
    pending_tickets = models.IntegerField(default=0)
    average_resolution_time = models.FloatField(default=0.0)
    total_points_awarded = models.IntegerField(default=0)
    
    # Top performers
    top_performer = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True)
    
    created_at = models.DateTimeField(auto_now_add=True)
    
    def __str__(self):
        return f"{self.report_type.title()} Report ({self.date_from} to {self.date_to})"
    
    class Meta:
        ordering = ['-created_at']


class EmailAccount(models.Model):
    """Email account configuration for automatic ticket creation"""
    PROTOCOL_CHOICES = [
        ('imap', 'IMAP'),
        ('pop3', 'POP3'),
    ]
    
    name = models.CharField(max_length=100, help_text="Display name for this email account")
    email_address = models.EmailField(unique=True)
    protocol = models.CharField(max_length=10, choices=PROTOCOL_CHOICES, default='imap')
    host = models.CharField(max_length=255, help_text="Email server hostname")
    port = models.IntegerField(default=993, help_text="Email server port")
    username = models.CharField(max_length=255, help_text="Username for email authentication")
    password = models.CharField(max_length=255, help_text="Password for email authentication")
    use_ssl = models.BooleanField(default=True, help_text="Use SSL/TLS encryption")
    
    # Ticket creation settings
    default_task_type = models.ForeignKey(TaskType, on_delete=models.CASCADE, help_text="Default task type for email tickets")
    default_task_category = models.ForeignKey(TaskCategory, on_delete=models.CASCADE, help_text="Default category for email tickets")
    default_priority = models.CharField(max_length=10, choices=WorkOrder.PRIORITY_CHOICES, default='medium')
    auto_assign_to = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True, help_text="Automatically assign tickets to this user")
    
    # Processing settings
    is_active = models.BooleanField(default=True, help_text="Enable/disable email processing for this account")
    last_processed = models.DateTimeField(null=True, blank=True, help_text="Last time emails were processed")
    processed_count = models.IntegerField(default=0, help_text="Total number of emails processed")
    
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    def clean(self):
        """Validate email address"""
        super().clean()
        try:
            validate_email(self.email_address)
        except EmailNotValidError as e:
            raise ValidationError({'email_address': str(e)})
    
    def __str__(self):
        return f"{self.name} ({self.email_address})"
    
    class Meta:
        ordering = ['name']
        verbose_name = "Email Account"
        verbose_name_plural = "Email Accounts"


class ProcessedEmail(models.Model):
    """Track processed emails to avoid duplicates"""
    email_account = models.ForeignKey(EmailAccount, on_delete=models.CASCADE, related_name='processed_emails')
    message_id = models.CharField(max_length=255, help_text="Email Message-ID header")
    subject = models.CharField(max_length=500)
    sender_email = models.EmailField()
    sender_name = models.CharField(max_length=255, blank=True)
    received_date = models.DateTimeField()
    processed_date = models.DateTimeField(auto_now_add=True)
    
    # Link to created work order
    work_order = models.ForeignKey(WorkOrder, on_delete=models.SET_NULL, null=True, blank=True, related_name='source_email')
    
    # Processing status
    processing_status = models.CharField(max_length=20, choices=[
        ('success', 'Success'),
        ('failed', 'Failed'),
        ('duplicate', 'Duplicate'),
        ('ignored', 'Ignored'),
    ], default='success')
    processing_notes = models.TextField(blank=True, help_text="Notes about processing result")
    
    def __str__(self):
        return f"{self.sender_email} - {self.subject[:50]}"
    
    class Meta:
        ordering = ['-received_date']
        unique_together = ['email_account', 'message_id']
        verbose_name = "Processed Email"
        verbose_name_plural = "Processed Emails"


class EmailTemplate(models.Model):
    """Email templates for automatic responses"""
    TEMPLATE_TYPES = [
        ('ticket_created', 'Ticket Created'),
        ('ticket_updated', 'Ticket Updated'),
        ('ticket_resolved', 'Ticket Resolved'),
        ('ticket_closed', 'Ticket Closed'),
    ]
    
    name = models.CharField(max_length=100)
    template_type = models.CharField(max_length=20, choices=TEMPLATE_TYPES)
    subject = models.CharField(max_length=255, help_text="Email subject (supports variables like {{ticket_number}})")
    body = models.TextField(help_text="Email body (supports variables like {{ticket_number}}, {{title}}, {{status}})")
    is_active = models.BooleanField(default=True)
    
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    def __str__(self):
        return f"{self.name} ({self.get_template_type_display()})"
    
    class Meta:
        ordering = ['name']
        unique_together = ['template_type']
        verbose_name = "Email Template"
        verbose_name_plural = "Email Templates"
