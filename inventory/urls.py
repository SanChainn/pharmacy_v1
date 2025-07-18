# inventory/urls.py

from django.urls import path
from django.contrib.auth import views as auth_views
from .views import (
    # New Views
    home_view,
    dashboard_view,

    # Inventory
    MedicineListView,
    MedicineCreateView,
    MedicineUpdateView,
    MedicineDeleteView,
    ThresholdUpdateView,
    
    # POS and Sales
    pos_view,
    sales_report_view,
    sale_receipt_view,
    
    # Staff Management
    manage_staff_view,
    manage_permissions_view,
    edit_staff_view,
    delete_staff_view,
    
    # Settings
    settings_view,
    
    # File Handling
    export_inventory_csv,
    upload_inventory_file,
    
    # Auth
    logout_view,
)

urlpatterns = [
    # Auth URLs
    path('login/', auth_views.LoginView.as_view(template_name='inventory/login.html'), name='login'),
    path('logout/', logout_view, name='logout'),

    # Main application URLs
    path('', home_view, name='home'),
    path('dashboard/', dashboard_view, name='dashboard'),
    path('inventory/', MedicineListView.as_view(), name='medicine_list'),
    path('inventory/new/', MedicineCreateView.as_view(), name='medicine_new'),
    path('inventory/<int:pk>/edit/', MedicineUpdateView.as_view(), name='medicine_edit'),
    path('inventory/<int:pk>/delete/', MedicineDeleteView.as_view(), name='medicine_delete'),
    
    # Thresholds
    path('thresholds/<int:pk>/edit/', ThresholdUpdateView.as_view(), name='threshold_edit'),
    
    # POS and Sales
    path('pos/', pos_view, name='pos'),
    path('sales/', sales_report_view, name='sales_report'),
    path('sales/receipt/<int:pk>/', sale_receipt_view, name='sale_receipt'),

    # Staff and Permission Management
    path('staff/', manage_staff_view, name='manage_staff'),
    path('staff/permissions/<int:user_id>/', manage_permissions_view, name='manage_permissions'),
    path('staff/edit/<int:user_id>/', edit_staff_view, name='edit_staff'),
    path('staff/delete/<int:user_id>/', delete_staff_view, name='delete_staff'),
    
    # Settings
    path('settings/', settings_view, name='settings'),

    # File Handling
    path('export/csv/', export_inventory_csv, name='export_inventory_csv'),
    path('upload/file/', upload_inventory_file, name='upload_inventory_file'),
]
