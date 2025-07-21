from django.shortcuts import render, get_object_or_404, redirect
from django.contrib.auth.decorators import login_required
from django.contrib.auth.models import User
from django.contrib import messages
from django.http import JsonResponse
from django.db.models import Count, Q, Avg
from django.utils import timezone
from datetime import datetime, timedelta
import folium
import json
from .models import (
    WorkOrder, WorkOrderComment, TaskType, TaskCategory, 
    UserProfile, KPIReport
)
from .forms import WorkOrderForm, WorkOrderCommentForm, WorkOrderStatusForm


def dashboard(request):
    """Main dashboard view"""
    # Get statistics
    total_tickets = WorkOrder.objects.count()
    open_tickets = WorkOrder.objects.filter(status='open').count()
    in_progress_tickets = WorkOrder.objects.filter(status='in_progress').count()
    resolved_tickets = WorkOrder.objects.filter(status='resolved').count()
    
    # Recent tickets
    recent_tickets = WorkOrder.objects.all()[:10]
    
    # Ticket stats by category
    category_stats = TaskCategory.objects.annotate(
        ticket_count=Count('workorder')
    ).values('name', 'ticket_count', 'color')
    
    # Top performers
    top_performers = UserProfile.objects.order_by('-total_points')[:5]
    
    # Create map with work order locations
    map_data = create_work_order_map()
    
    context = {
        'total_tickets': total_tickets,
        'open_tickets': open_tickets,
        'in_progress_tickets': in_progress_tickets,
        'resolved_tickets': resolved_tickets,
        'recent_tickets': recent_tickets,
        'category_stats': category_stats,
        'top_performers': top_performers,
        'map_html': map_data,
    }
    return render(request, 'workorders/dashboard.html', context)


@login_required
def work_order_list(request):
    """List all work orders"""
    work_orders = WorkOrder.objects.all()
    
    # Filter by status
    status_filter = request.GET.get('status')
    if status_filter:
        work_orders = work_orders.filter(status=status_filter)
    
    # Filter by assigned user
    assigned_filter = request.GET.get('assigned')
    if assigned_filter:
        work_orders = work_orders.filter(assigned_to_id=assigned_filter)
    
    # Filter by task type
    task_type_filter = request.GET.get('task_type')
    if task_type_filter:
        work_orders = work_orders.filter(task_type_id=task_type_filter)
    
    # Search
    search = request.GET.get('search')
    if search:
        work_orders = work_orders.filter(
            Q(title__icontains=search) | 
            Q(description__icontains=search) |
            Q(ticket_number__icontains=search)
        )
    
    # Get filter options
    task_types = TaskType.objects.all()
    staff_users = User.objects.filter(is_staff=True)
    
    context = {
        'work_orders': work_orders,
        'task_types': task_types,
        'staff_users': staff_users,
        'status_choices': WorkOrder.STATUS_CHOICES,
    }
    return render(request, 'workorders/work_order_list.html', context)


@login_required
def work_order_detail(request, pk):
    """Work order detail view"""
    work_order = get_object_or_404(WorkOrder, pk=pk)
    comments = work_order.comments.all()
    
    # Handle comment submission
    if request.method == 'POST' and 'add_comment' in request.POST:
        comment_form = WorkOrderCommentForm(request.POST)
        if comment_form.is_valid():
            comment = comment_form.save(commit=False)
            comment.work_order = work_order
            comment.author = request.user
            comment.save()
            messages.success(request, 'Comment added successfully!')
            return redirect('work_order_detail', pk=pk)
    else:
        comment_form = WorkOrderCommentForm()
    
    # Handle status update
    if request.method == 'POST' and 'update_status' in request.POST:
        status_form = WorkOrderStatusForm(request.POST, instance=work_order)
        if status_form.is_valid():
            work_order = status_form.save()
            messages.success(request, 'Status updated successfully!')
            
            # Add success message for point distribution if work order was resolved
            if work_order.status == 'resolved':
                assignees = work_order.assigned_to.all()
                if assignees and work_order.points_earned > 0:
                    points_per_user = work_order.points_earned // len(assignees)
                    messages.success(request, f'Points distributed: {points_per_user} points to each assignee!')
            
            return redirect('work_order_detail', pk=pk)
    else:
        status_form = WorkOrderStatusForm(instance=work_order)
    
    # Create location map if coordinates exist
    location_map = None
    if work_order.latitude and work_order.longitude:
        m = folium.Map(
            location=[work_order.latitude, work_order.longitude],
            zoom_start=15
        )
        folium.Marker(
            [work_order.latitude, work_order.longitude],
            popup=f"{work_order.ticket_number}: {work_order.title}",
            tooltip=work_order.location_name
        ).add_to(m)
        location_map = m._repr_html_()
    
    context = {
        'work_order': work_order,
        'comments': comments,
        'comment_form': comment_form,
        'status_form': status_form,
        'location_map': location_map,
    }
    return render(request, 'workorders/work_order_detail.html', context)


@login_required
def work_order_create(request):
    """Create new work order"""
    if request.method == 'POST':
        form = WorkOrderForm(request.POST, user=request.user)
        if form.is_valid():
            work_order = form.save(commit=False)
            work_order.requester = request.user
            work_order.save()
            form.save_m2m()  # Save many-to-many relationships
            messages.success(request, f'Work order {work_order.ticket_number} created successfully!')
            return redirect('work_order_detail', pk=work_order.pk)
    else:
        form = WorkOrderForm(user=request.user)
    
    return render(request, 'workorders/work_order_form.html', {'form': form})


@login_required
def work_order_edit(request, pk):
    """Edit work order"""
    work_order = get_object_or_404(WorkOrder, pk=pk)
    
    if request.method == 'POST':
        form = WorkOrderForm(request.POST, instance=work_order)
        if form.is_valid():
            form.save()
            messages.success(request, 'Work order updated successfully!')
            return redirect('work_order_detail', pk=pk)
    else:
        form = WorkOrderForm(instance=work_order)
    
    return render(request, 'workorders/work_order_form.html', {
        'form': form,
        'work_order': work_order
    })


@login_required
def user_profile(request, user_id=None):
    """User profile with gamification stats"""
    if user_id:
        user = get_object_or_404(User, id=user_id)
    else:
        user = request.user
    
    profile, created = UserProfile.objects.get_or_create(user=user)
    
    # Get user's tickets
    requested_tickets = WorkOrder.objects.filter(requester=user)
    assigned_tickets = WorkOrder.objects.filter(assigned_to=user)
    
    # Get badges
    badges = profile.get_badges()
    
    # Calculate progress to next level
    next_level_points = profile.level * 1000
    progress_percentage = (profile.total_points % 1000) / 1000 * 100
    
    context = {
        'profile_user': user,
        'profile': profile,
        'requested_tickets': requested_tickets,
        'assigned_tickets': assigned_tickets,
        'badges': badges,
        'next_level_points': next_level_points,
        'progress_percentage': progress_percentage,
    }
    return render(request, 'workorders/user_profile.html', context)


@login_required
def leaderboard(request):
    """Leaderboard view"""
    profiles = UserProfile.objects.select_related('user').order_by('-total_points')[:20]
    
    context = {
        'profiles': profiles,
    }
    return render(request, 'workorders/leaderboard.html', context)


@login_required
def kpi_report(request):
    """KPI report view"""
    # Get date range from request
    end_date = datetime.now().date()
    start_date = end_date - timedelta(days=30)  # Default to last 30 days
    
    if request.GET.get('start_date'):
        start_date = datetime.strptime(request.GET.get('start_date'), '%Y-%m-%d').date()
    if request.GET.get('end_date'):
        end_date = datetime.strptime(request.GET.get('end_date'), '%Y-%m-%d').date()
    
    # Calculate KPIs
    work_orders = WorkOrder.objects.filter(
        created_at__date__range=[start_date, end_date]
    )
    
    total_tickets = work_orders.count()
    resolved_tickets = work_orders.filter(status='resolved').count()
    pending_tickets = work_orders.exclude(status__in=['resolved', 'closed']).count()
    
    # Average resolution time
    resolved_orders = work_orders.filter(status='resolved', resolved_at__isnull=False)
    avg_resolution_time = 0
    if resolved_orders.exists():
        resolution_times = []
        for order in resolved_orders:
            if order.resolved_at:
                time_diff = order.resolved_at - order.created_at
                resolution_times.append(time_diff.total_seconds() / 3600)  # Convert to hours
        if resolution_times:
            avg_resolution_time = sum(resolution_times) / len(resolution_times)
    
    # Top performer
    top_performer = None
    performer_stats = UserProfile.objects.filter(
        user__assigned_tickets__created_at__date__range=[start_date, end_date]
    ).annotate(
        tickets_in_period=Count('user__assigned_tickets')
    ).order_by('-tickets_in_period').first()
    
    if performer_stats:
        top_performer = performer_stats.user
    
    # Charts data
    status_data = {
        'labels': ['Open', 'In Progress', 'Resolved', 'Closed'],
        'data': [
            work_orders.filter(status='open').count(),
            work_orders.filter(status='in_progress').count(),
            work_orders.filter(status='resolved').count(),
            work_orders.filter(status='closed').count(),
        ]
    }
    
    priority_data = {
        'labels': ['Low', 'Medium', 'High', 'Urgent'],
        'data': [
            work_orders.filter(priority='low').count(),
            work_orders.filter(priority='medium').count(),
            work_orders.filter(priority='high').count(),
            work_orders.filter(priority='urgent').count(),
        ]
    }
    
    context = {
        'start_date': start_date,
        'end_date': end_date,
        'total_tickets': total_tickets,
        'resolved_tickets': resolved_tickets,
        'pending_tickets': pending_tickets,
        'avg_resolution_time': round(avg_resolution_time, 2),
        'top_performer': top_performer,
        'status_data': json.dumps(status_data),
        'priority_data': json.dumps(priority_data),
    }
    return render(request, 'workorders/kpi_report.html', context)


def create_work_order_map():
    """Create a map with all work order locations"""
    # Get work orders with location data
    work_orders = WorkOrder.objects.filter(
        latitude__isnull=False,
        longitude__isnull=False
    )
    
    if not work_orders.exists():
        return None
    
    # Calculate center point
    center_lat = sum(wo.latitude for wo in work_orders) / len(work_orders)
    center_lng = sum(wo.longitude for wo in work_orders) / len(work_orders)
    
    # Create map
    m = folium.Map(location=[center_lat, center_lng], zoom_start=10)
    
    # Add markers for each work order
    for wo in work_orders:
        color = {
            'open': 'red',
            'in_progress': 'orange',
            'waiting': 'yellow',
            'resolved': 'green',
            'closed': 'blue'
        }.get(wo.status, 'gray')
        
        folium.Marker(
            [wo.latitude, wo.longitude],
            popup=f"""<b>{wo.ticket_number}</b><br>
                     {wo.title}<br>
                     Status: {wo.get_status_display()}<br>
                     Priority: {wo.get_priority_display()}""",
            tooltip=wo.location_name,
            icon=folium.Icon(color=color)
        ).add_to(m)
    
    return m._repr_html_()


@login_required
def geocode_location(request):
    """Geocode location using a free service"""
    if request.method != 'POST':
        return JsonResponse({'success': False, 'error': 'Only POST requests are allowed'})
    
    location_name = request.POST.get('location_name')
    if not location_name or not location_name.strip():
        return JsonResponse({'success': False, 'error': 'Please provide a location name'})
    
    try:
        import requests
        from urllib.parse import quote_plus
        
        # URL encode the location name to handle special characters
        encoded_location = quote_plus(location_name.strip())
        
        # Using OpenStreetMap Nominatim API (free)
        url = f"https://nominatim.openstreetmap.org/search?format=json&q={encoded_location}&limit=1&addressdetails=1"
        
        # Make the request with proper headers and timeout
        response = requests.get(
            url, 
            headers={
                'User-Agent': 'IT-Support-System/1.0 (Django Application)',
                'Accept': 'application/json'
            },
            timeout=10  # 10 second timeout
        )
        
        # Check if the request was successful
        if response.status_code != 200:
            return JsonResponse({
                'success': False,
                'error': f'Geocoding service returned status {response.status_code}'
            })
        
        # Parse the JSON response
        data = response.json()
        
        if data and len(data) > 0:
            location = data[0]
            return JsonResponse({
                'success': True,
                'latitude': float(location['lat']),
                'longitude': float(location['lon']),
                'display_name': location.get('display_name', location_name),
                'raw_data': location  # For debugging
            })
        else:
            return JsonResponse({
                'success': False,
                'error': f'No results found for "{location_name}". Try being more specific or use a different search term.'
            })
            
    except requests.exceptions.Timeout:
        return JsonResponse({
            'success': False,
            'error': 'Request timed out. Please try again.'
        })
    except requests.exceptions.ConnectionError:
        return JsonResponse({
            'success': False,
            'error': 'Could not connect to geocoding service. Please check your internet connection.'
        })
    except requests.exceptions.RequestException as e:
        return JsonResponse({
            'success': False,
            'error': f'Network error: {str(e)}'
        })
    except ValueError as e:
        return JsonResponse({
            'success': False,
            'error': f'Invalid response from geocoding service: {str(e)}'
        })
    except Exception as e:
        return JsonResponse({
            'success': False,
            'error': f'Unexpected error: {str(e)}'
        })


@login_required
def test_endpoint(request):
    """Simple test endpoint to verify connectivity and CSRF"""
    return JsonResponse({
        'success': True,
        'message': 'Test endpoint working',
        'method': request.method,
        'user': request.user.username if request.user.is_authenticated else 'Anonymous'
    })
