# inventory/views.py

from django.shortcuts import render, get_object_or_404, redirect
from django.urls import reverse_lazy
from django.views.generic import ListView, CreateView, UpdateView, DeleteView
from django.db import transaction, IntegrityError
from django.db.models import Sum, F, ProtectedError
from django.http import JsonResponse, HttpResponse
from django.contrib import messages
import json
import csv
import pandas as pd
from datetime import date, timedelta
from django.contrib.auth import logout
from django.contrib.auth.mixins import LoginRequiredMixin, UserPassesTestMixin
from django.contrib.auth.decorators import login_required, user_passes_test
from django.contrib.auth.models import User, Permission
from django.contrib.contenttypes.models import ContentType
from collections import OrderedDict

# Import all models and forms
from .models import Medicine, Sale, SaleItem, Threshold, Profile, PharmacyInfo
from .forms import (
    MedicineForm, 
    ThresholdForm, 
    StaffCreationForm, 
    FileUploadForm, 
    StaffPasswordChangeForm,
    PharmacyInfoForm
)

# --- New Views for Dashboard and Home ---
@login_required
def home_view(request):
    """Redirects authenticated users to the dashboard, others to login."""
    if request.user.is_authenticated:
        return redirect('dashboard')
    return redirect('login')

@login_required
def dashboard_view(request):
    """Displays the main dashboard with navigation icons."""
    return render(request, 'inventory/dashboard.html')


# --- Custom Logout View ---
def logout_view(request):
    """Logs the user out and redirects them to the login page."""
    logout(request)
    messages.info(request, "You have been successfully logged out.")
    return redirect('login')

# --- Helper Functions for Permissions ---
def is_admin(user):
    """Checks if a user is authenticated and has the 'admin' role."""
    return user.is_authenticated and hasattr(user, 'profile') and user.profile.role == 'admin'

def user_has_permission(user, perm_codename):
    """Checks if a user has a specific permission. Admins have all permissions implicitly."""
    if not user.is_authenticated or not hasattr(user, 'profile'):
        return False
    if is_admin(user):
        return True
    return user.profile.permissions.filter(codename=perm_codename).exists()

class PermissionRequiredMixin(LoginRequiredMixin, UserPassesTestMixin):
    """A mixin for class-based views that requires a specific permission."""
    permission_required = None
    login_url = '/login/' 

    def test_func(self):
        if self.permission_required is None:
            return False
        return user_has_permission(self.request.user, self.permission_required)

# --- Settings View ---
@login_required
@user_passes_test(is_admin)
def settings_view(request):
    """Handles updating pharmacy-wide settings."""
    pharmacy_info, _ = PharmacyInfo.objects.get_or_create(pk=1)
    if request.method == 'POST':
        form = PharmacyInfoForm(request.POST, instance=pharmacy_info)
        if form.is_valid():
            form.save()
            messages.success(request, "Pharmacy information updated successfully.")
            return redirect('settings')
    else:
        form = PharmacyInfoForm(instance=pharmacy_info)
    
    context = {'form': form, 'pharmacy_info': pharmacy_info}
    return render(request, 'inventory/settings.html', context)

# --- Staff and Permission Management Views ---
@login_required
@user_passes_test(is_admin)
def manage_staff_view(request):
    """Handles both displaying the list of staff and creating new staff members."""
    if request.method == 'POST':
        form = StaffCreationForm(request.POST)
        if form.is_valid():
            form.save()
            messages.success(request, f"Staff account for '{form.cleaned_data['username']}' created successfully.")
            return redirect('manage_staff')
        else:
            messages.error(request, 'Please correct the errors below.')
    else:
        form = StaffCreationForm()

    staff_list = User.objects.filter(profile__role__in=['staff', 'admin'])
    context = {'staff_list': staff_list, 'form': form}
    return render(request, 'inventory/manage_staff.html', context)

@login_required
@user_passes_test(is_admin)
def edit_staff_view(request, user_id):
    """Handles changing a staff member's password."""
    staff_user = get_object_or_404(User, pk=user_id, profile__role__in=['staff', 'admin'])
    if request.method == 'POST':
        form = StaffPasswordChangeForm(request.POST)
        if form.is_valid():
            new_password = form.cleaned_data['password']
            staff_user.set_password(new_password)
            staff_user.save()
            messages.success(request, f"Password for {staff_user.username} has been updated successfully.")
            return redirect('manage_staff')
    else:
        form = StaffPasswordChangeForm()

    context = {'form': form, 'staff_user': staff_user}
    return render(request, 'inventory/edit_staff.html', context)


@login_required
@user_passes_test(is_admin)
def delete_staff_view(request, user_id):
    """Deletes a staff member, preventing a user from deleting themselves."""
    if request.user.id == user_id:
        messages.error(request, "You cannot delete your own account.")
        return redirect('manage_staff')

    staff = get_object_or_404(User, id=user_id)
    if request.method == 'POST':
        staff_username = staff.username
        staff.delete()
        messages.success(request, f"User '{staff_username}' has been deleted successfully.")
        return redirect('manage_staff')
        
    return render(request, 'inventory/delete_staff_confirm.html', {'staff': staff})


@login_required
@user_passes_test(is_admin)
def manage_permissions_view(request, user_id):
    """Manages the permissions for a specific staff member."""
    staff_user = get_object_or_404(User, pk=user_id, profile__role__in=['staff', 'admin'])
    
    if staff_user.profile.role == 'admin':
        messages.info(request, "Admin users have all permissions by default and cannot be edited.")
        return redirect('manage_staff')

    app_content_types = ContentType.objects.filter(app_label='inventory')
    permissions = Permission.objects.filter(content_type__in=app_content_types)

    if request.method == 'POST':
        permission_ids = request.POST.getlist('permissions')
        staff_user.profile.permissions.set(permission_ids)
        messages.success(request, f"Permissions for {staff_user.username} updated successfully.")
        return redirect('manage_staff')

    context = {
        'staff_user': staff_user,
        'permissions': permissions,
        'staff_permissions': staff_user.profile.permissions.all()
    }
    return render(request, 'inventory/manage_permissions.html', context)

# --- Inventory Views ---
class MedicineListView(LoginRequiredMixin, ListView):
    model = Medicine
    template_name = 'inventory/medicine_list.html'
    context_object_name = 'medicines'
    login_url = '/login/'

    def get_queryset(self):
        """
        MODIFIED: This now only shows active medicines in the main inventory list.
        """
        return Medicine.objects.filter(is_active=True)

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        thresholds, _ = Threshold.objects.get_or_create(pk=1)
        
        medicines = self.get_queryset()
        expiry_alert_date = date.today() + timedelta(days=thresholds.expiry_threshold_days)

        for med in medicines:
            med.is_low_stock = med.quantity <= thresholds.low_stock_threshold
            med.is_expiring_soon = med.expiry_date <= expiry_alert_date
        
        context.update({
            'low_stock_medicines': [m for m in medicines if m.is_low_stock],
            'expiring_soon_medicines': [m for m in medicines if m.is_expiring_soon],
            'thresholds': thresholds,
            'upload_form': FileUploadForm(),
            'user_can_add': user_has_permission(self.request.user, 'add_medicine'),
            'user_can_edit': user_has_permission(self.request.user, 'change_medicine'),
            'user_can_delete': user_has_permission(self.request.user, 'delete_medicine'),
            'user_can_adjust_thresholds': user_has_permission(self.request.user, 'change_threshold'),
            'is_admin': is_admin(self.request.user)
        })
        return context

class MedicineCreateView(PermissionRequiredMixin, CreateView):
    permission_required = 'add_medicine'
    model = Medicine
    form_class = MedicineForm
    template_name = 'inventory/medicine_form.html'
    success_url = reverse_lazy('medicine_list')

class MedicineUpdateView(PermissionRequiredMixin, UpdateView):
    permission_required = 'change_medicine'
    model = Medicine
    form_class = MedicineForm
    template_name = 'inventory/medicine_form.html'
    success_url = reverse_lazy('medicine_list')

class MedicineDeleteView(PermissionRequiredMixin, DeleteView):
    permission_required = 'delete_medicine'
    model = Medicine
    template_name = 'inventory/medicine_confirm_delete.html'
    success_url = reverse_lazy('medicine_list')

    def post(self, request, *args, **kwargs):
        """
        MODIFIED: This method no longer deletes the object.
        It sets the 'is_active' flag to False.
        """
        medicine = self.get_object()
        medicine.is_active = False
        medicine.save()
        messages.success(request, f"Successfully removed '{medicine.name}' from the active inventory.")
        return redirect(self.success_url)


class ThresholdUpdateView(PermissionRequiredMixin, UpdateView):
    permission_required = 'change_threshold'
    model = Threshold
    form_class = ThresholdForm
    template_name = 'inventory/threshold_form.html'
    success_url = reverse_lazy('medicine_list')

# --- POS and Sales Views ---
@login_required(login_url='/login/')
def pos_view(request):
    if not user_has_permission(request.user, 'add_sale'):
        messages.error(request, "You do not have permission to access the Point of Sale.")
        return redirect('dashboard')
        
    if request.method == 'POST':
        try:
            data = json.loads(request.body)
            cart_data = data.get('cart', [])
            delivery_fee = int(data.get('delivery_fee', 0))
            customer_name = data.get('customer_name', '')
            customer_phone = data.get('customer_phone', '')
            customer_address = data.get('customer_address', '')
            sale_id = data.get('sale_id')

            with transaction.atomic():
                if sale_id and user_has_permission(request.user, 'change_sale'):
                    sale = get_object_or_404(Sale, pk=sale_id)
                    # Return old items to stock before deleting them
                    for old_item in sale.items.all():
                        old_item.medicine.quantity = F('quantity') + old_item.quantity
                        old_item.medicine.save(update_fields=['quantity'])
                    sale.items.all().delete()
                else:
                    sale = Sale.objects.create()

                sale.created_by = request.user
                sale.delivery_fee = delivery_fee
                sale.customer_name = customer_name
                sale.customer_phone = customer_phone
                sale.customer_address = customer_address
                sale.save()

                for item_data in cart_data:
                    medicine = Medicine.objects.get(pk=item_data['id'])
                    quantity_sold = int(item_data['quantity'])
                    price_at_sale = int(item_data['price'])

                    if medicine.quantity < quantity_sold:
                        raise ValueError(f"Not enough stock for {medicine.name}.")

                    SaleItem.objects.create(
                        sale=sale,
                        medicine=medicine,
                        quantity=quantity_sold,
                        price_at_sale=price_at_sale
                    )
                    
                    medicine.quantity = F('quantity') - quantity_sold
                    medicine.save(update_fields=['quantity'])
                
                sale.update_total()
            return JsonResponse({'status': 'success', 'message': 'Sale completed!', 'sale_id': sale.pk})
        except Exception as e:
            return JsonResponse({'status': 'error', 'message': str(e)}, status=400)

    # MODIFIED: Ensure only active medicines are available for sale.
    medicines = Medicine.objects.filter(quantity__gt=0, is_active=True)
    
    sale_to_modify = None
    sale_id = request.GET.get('sale_id')
    if sale_id and user_has_permission(request.user, 'change_sale'):
        try:
            sale_to_modify = Sale.objects.get(pk=sale_id)
        except Sale.DoesNotExist:
            pass 

    return render(request, 'inventory/pos.html', {'medicines': medicines, 'sale_to_modify': sale_to_modify})

@login_required(login_url='/login/')
def sales_report_view(request):
    """
    Groups sales by month for a categorized report.
    """
    if not user_has_permission(request.user, 'view_sale'):
        messages.error(request, "You do not have permission to view sales reports.")
        return redirect('dashboard')

    sales_query = Sale.objects.select_related('created_by').all().order_by('-created_at')

    # Create an ordered dictionary to hold sales grouped by month
    sales_by_month = OrderedDict()

    for sale in sales_query:
        # Get the first day of the month for the sale's creation date
        month_start = sale.created_at.date().replace(day=1)
        if month_start not in sales_by_month:
            sales_by_month[month_start] = {
                'sales': [],
                'monthly_total': 0
            }
        sales_by_month[month_start]['sales'].append(sale)
        sales_by_month[month_start]['monthly_total'] += sale.total_amount

    total_revenue = sales_query.aggregate(total=Sum('total_amount'))['total'] or 0

    context = {
        'sales_by_month': sales_by_month,
        'total_revenue': total_revenue,
    }
    return render(request, 'inventory/sales_report.html', context)


@login_required(login_url='/login/')
def sale_receipt_view(request, pk):
    if not user_has_permission(request.user, 'view_sale'):
        return redirect('dashboard')
    sale = get_object_or_404(Sale, pk=pk)
    pharmacy_info, _ = PharmacyInfo.objects.get_or_create(pk=1)
    return render(request, 'inventory/sale_receipt.html', {'sale': sale, 'pharmacy_info': pharmacy_info})

# --- File Handling Views ---
@login_required
@user_passes_test(is_admin)
def export_inventory_csv(request):
    response = HttpResponse(content_type='text/csv')
    response['Content-Disposition'] = 'attachment; filename="inventory_export.csv"'

    writer = csv.writer(response)
    # Write the header row
    writer.writerow([
        'Code', 'Name', 'Brand', 'Category', 'Units per Package', 'Package Type',
        'Stock Quantity', 'Purchase Price', 'Selling Price', 'Purchase Date', 'Expiry Date'
    ])

    # Write data rows
    medicines = Medicine.objects.all()
    for medicine in medicines:
        writer.writerow([
            medicine.code,
            medicine.name,
            medicine.brand_name,
            medicine.get_category_display(),
            medicine.unit_per_package,
            medicine.package_type,
            medicine.quantity,
            medicine.purchase_price,
            medicine.selling_price,
            medicine.purchase_date,
            medicine.expiry_date,
        ])

    return response

@login_required
@user_passes_test(is_admin)
def upload_inventory_file(request):
    if request.method != 'POST':
        return redirect('dashboard')

    form = FileUploadForm(request.POST, request.FILES)
    if not form.is_valid():
        messages.error(request, 'There was an error with the form. Please select a file.')
        return redirect('medicine_list')

    file = form.cleaned_data['file']
    
    try:
        if file.name.endswith('.csv'):
            # Use utf-8-sig to handle potential BOM (Byte Order Mark) in CSV files
            df = pd.read_csv(file, encoding='utf-8-sig', keep_default_na=False)
        elif file.name.endswith(('.xls', '.xlsx')):
            df = pd.read_excel(file, engine='openpyxl', keep_default_na=False)
        else:
            messages.error(request, 'Error: Unsupported file format. Please upload a CSV or Excel file.')
            return redirect('medicine_list')

        # Normalize column names
        df.columns = df.columns.str.lower().str.replace(' ', '_').str.replace('(', '').str.replace(')', '')
        
        expected_columns = ['code', 'name', 'expiry_date']
        if not all(col in df.columns for col in expected_columns):
            missing = [col for col in expected_columns if col not in df.columns]
            messages.error(request, f'Missing required columns in the uploaded file: {", ".join(missing)}')
            return redirect('medicine_list')

        category_map = {v.lower(): k for k, v in Medicine.CATEGORY_CHOICES}

        with transaction.atomic():
            for index, row in df.iterrows():
                code = row.get('code')
                if not code: continue

                try:
                    expiry_date = pd.to_datetime(row['expiry_date']).date() if pd.notna(row['expiry_date']) else None
                    if not expiry_date: continue
                except ValueError:
                    messages.warning(request, f"Skipping row {index+2} due to invalid date format for expiry_date.")
                    continue

                Medicine.objects.update_or_create(
                    code=code,
                    defaults={
                        'name': row.get('name', ''),
                        'brand_name': row.get('brand_name', row.get('brand', '')),
                        'category': category_map.get(str(row.get('category', '')).lower(), 'Other'),
                        'unit_per_package': int(row.get('units_per_package', row.get('units/pkg', 1))),
                        'package_type': row.get('package_type', ''),
                        'quantity': int(row.get('stock_quantity', row.get('stock', 0))),
                        'purchase_price': int(row.get('purchase_price', row.get('buy_price', 0))),
                        'selling_price': int(row.get('selling_price', row.get('sell_price', 0))),
                        'purchase_date': pd.to_datetime(row.get('purchase_date', row.get('buy_date'))).date() if pd.notna(row.get('purchase_date', row.get('buy_date'))) else None,
                        'expiry_date': expiry_date,
                    }
                )
        messages.success(request, 'Inventory successfully updated from the uploaded file.')
    except Exception as e:
        messages.error(request, f'An error occurred during file processing: {e}')
    
    return redirect('medicine_list')