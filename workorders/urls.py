from django.urls import path
from . import views

urlpatterns = [
    path('', views.dashboard, name='dashboard'),
    path('work-orders/', views.work_order_list, name='work_order_list'),
    path('work-orders/create/', views.work_order_create, name='work_order_create'),
    path('work-orders/<int:pk>/', views.work_order_detail, name='work_order_detail'),
    path('work-orders/<int:pk>/edit/', views.work_order_edit, name='work_order_edit'),
    path('profile/', views.user_profile, name='user_profile'),
    path('profile/<int:user_id>/', views.user_profile, name='user_profile_detail'),
    path('leaderboard/', views.leaderboard, name='leaderboard'),
    path('kpi-report/', views.kpi_report, name='kpi_report'),
    path('geocode/', views.geocode_location, name='geocode_location'),
    path('test-endpoint/', views.test_endpoint, name='test_endpoint'),
]
