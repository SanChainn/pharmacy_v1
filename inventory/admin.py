# inventory/admin.py

from django.contrib import admin
from .models import Profile, Threshold, Medicine, Sale, SaleItem, PharmacyInfo

# Register your models here to make them accessible in the Django admin interface.

class SaleItemInline(admin.TabularInline):
    """Allows editing of SaleItems directly within the Sale admin page."""
    model = SaleItem
    extra = 0 # Don't show any extra empty forms

class SaleAdmin(admin.ModelAdmin):
    """Customizes the display of the Sale model in the admin."""
    list_display = ('id', 'customer_name', 'total_amount', 'created_at')
    inlines = [SaleItemInline]

class MedicineAdmin(admin.ModelAdmin):
    """Customizes the display of the Medicine model in the admin."""
    list_display = ('name', 'brand_name', 'quantity', 'selling_price', 'expiry_date')
    search_fields = ('name', 'brand_name', 'code')

admin.site.register(Profile)
admin.site.register(Threshold)
admin.site.register(Medicine, MedicineAdmin)
admin.site.register(Sale, SaleAdmin)
admin.site.register(PharmacyInfo)
