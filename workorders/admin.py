from django.contrib import admin
from django.contrib.auth.models import User
from django.contrib.auth.admin import UserAdmin
from .models import (
    TaskType, TaskCategory, WorkOrder, WorkOrderComment, 
    UserProfile, KPIReport, EmailAccount, ProcessedEmail, EmailTemplate
)


@admin.register(TaskType)
class TaskTypeAdmin(admin.ModelAdmin):
    list_display = ['name', 'points_base', 'created_at']
    search_fields = ['name']
    ordering = ['name']


@admin.register(TaskCategory)
class TaskCategoryAdmin(admin.ModelAdmin):
    list_display = ['name', 'color', 'multiplier', 'created_at']
    search_fields = ['name']
    ordering = ['name']


class WorkOrderCommentInline(admin.TabularInline):
    model = WorkOrderComment
    extra = 0
    readonly_fields = ['created_at']


@admin.register(WorkOrder)
class WorkOrderAdmin(admin.ModelAdmin):
    list_display = [
        'ticket_number', 'title', 'task_type', 'task_category', 
        'priority', 'status', 'get_assignees', 'created_at', 'points_earned'
    ]
    list_filter = ['task_type', 'task_category', 'priority', 'status', 'created_at']
    search_fields = ['ticket_number', 'title', 'description']
    readonly_fields = ['ticket_number', 'points_earned', 'created_at', 'updated_at']
    inlines = [WorkOrderCommentInline]
    ordering = ['-created_at']
    
    fieldsets = (
        ('Basic Information', {
            'fields': ('ticket_number', 'title', 'description')
        }),
        ('Classification', {
            'fields': ('task_type', 'task_category', 'priority', 'difficulty_rating')
        }),
        ('Assignment', {
            'fields': ('requester', 'assigned_to', 'status')
        }),
        ('Location', {
            'fields': ('location_name', 'latitude', 'longitude')
        }),
        ('Time Tracking', {
            'fields': ('created_at', 'updated_at', 'due_date', 'resolved_at')
        }),
        ('Gamification', {
            'fields': ('points_earned',)
        }),
    )
    
    def get_assignees(self, obj):
        """Display all assigned users"""
        assignees = obj.assigned_to.all()
        if assignees:
            return ", ".join([user.username for user in assignees])
        return "None"
    get_assignees.short_description = "Assigned To"


@admin.register(UserProfile)
class UserProfileAdmin(admin.ModelAdmin):
    list_display = ['user', 'level', 'total_points', 'tickets_resolved', 'average_resolution_time']
    list_filter = ['level']
    search_fields = ['user__username', 'user__email']
    readonly_fields = ['total_points', 'level', 'badges']
    ordering = ['-total_points']


@admin.register(KPIReport)
class KPIReportAdmin(admin.ModelAdmin):
    list_display = [
        'report_type', 'date_from', 'date_to', 'total_tickets', 
        'resolved_tickets', 'top_performer', 'created_at'
    ]
    list_filter = ['report_type', 'created_at']
    ordering = ['-created_at']


# Extend User admin to include profile
class UserProfileInline(admin.StackedInline):
    model = UserProfile
    can_delete = False
    verbose_name_plural = 'Profile'


class CustomUserAdmin(UserAdmin):
    inlines = (UserProfileInline,)


@admin.register(EmailAccount)
class EmailAccountAdmin(admin.ModelAdmin):
    list_display = [
        'name', 'email_address', 'protocol', 'host', 'port', 
        'is_active', 'last_processed', 'processed_count'
    ]
    list_filter = ['protocol', 'is_active', 'use_ssl']
    search_fields = ['name', 'email_address', 'host']
    readonly_fields = ['last_processed', 'processed_count', 'created_at', 'updated_at']
    ordering = ['name']
    
    fieldsets = (
        ('Basic Information', {
            'fields': ('name', 'email_address', 'is_active')
        }),
        ('Server Configuration', {
            'fields': ('protocol', 'host', 'port', 'use_ssl')
        }),
        ('Authentication', {
            'fields': ('username', 'password'),
            'classes': ('collapse',)
        }),
        ('Ticket Settings', {
            'fields': ('default_task_type', 'default_task_category', 'default_priority', 'auto_assign_to')
        }),
        ('Statistics', {
            'fields': ('last_processed', 'processed_count', 'created_at', 'updated_at'),
            'classes': ('collapse',)
        }),
    )


class ProcessedEmailInline(admin.TabularInline):
    model = ProcessedEmail
    extra = 0
    readonly_fields = ['message_id', 'subject', 'sender_email', 'received_date', 'processed_date', 'processing_status']
    fields = ['subject', 'sender_email', 'received_date', 'processing_status', 'work_order']
    can_delete = False


@admin.register(ProcessedEmail)
class ProcessedEmailAdmin(admin.ModelAdmin):
    list_display = [
        'subject', 'sender_email', 'sender_name', 'email_account', 
        'processing_status', 'received_date', 'processed_date', 'work_order'
    ]
    list_filter = ['processing_status', 'email_account', 'received_date']
    search_fields = ['subject', 'sender_email', 'sender_name', 'message_id']
    readonly_fields = ['message_id', 'received_date', 'processed_date']
    ordering = ['-received_date']
    
    fieldsets = (
        ('Email Information', {
            'fields': ('email_account', 'message_id', 'subject', 'sender_email', 'sender_name', 'received_date')
        }),
        ('Processing', {
            'fields': ('processing_status', 'processing_notes', 'processed_date', 'work_order')
        }),
    )


@admin.register(EmailTemplate)
class EmailTemplateAdmin(admin.ModelAdmin):
    list_display = ['name', 'template_type', 'is_active', 'created_at']
    list_filter = ['template_type', 'is_active']
    search_fields = ['name', 'subject', 'body']
    ordering = ['name']
    
    fieldsets = (
        ('Basic Information', {
            'fields': ('name', 'template_type', 'is_active')
        }),
        ('Email Content', {
            'fields': ('subject', 'body'),
            'description': 'You can use variables like {{ticket_number}}, {{title}}, {{status}}, {{priority}}, {{requester}}, {{assigned_to}}, {{created_at}}'
        }),
        ('Timestamps', {
            'fields': ('created_at', 'updated_at'),
            'classes': ('collapse',)
        }),
    )
    
    readonly_fields = ['created_at', 'updated_at']


# Re-register UserAdmin
admin.site.unregister(User)
admin.site.register(User, CustomUserAdmin)
