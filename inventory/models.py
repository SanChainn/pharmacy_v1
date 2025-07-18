# inventory/models.py

from django.db import models
from django.utils import timezone
from datetime import timedelta
from django.contrib.auth.models import User, Permission
from django.db.models.signals import post_save
from django.dispatch import receiver

class Profile(models.Model):
    """
    Extends the default User model to include roles and permissions.
    """
    user = models.OneToOneField(User, on_delete=models.CASCADE)
    ROLE_CHOICES = (
        ('admin', 'Admin'),
        ('staff', 'Staff'),
    )
    role = models.CharField(max_length=10, choices=ROLE_CHOICES, blank=True)
    permissions = models.ManyToManyField(Permission, blank=True)

    def __str__(self):
        return f"{self.user.username} - {self.get_role_display()}"

@receiver(post_save, sender=User)
def create_or_update_user_profile(sender, instance, created, **kwargs):
    """
    A signal that automatically creates or updates a user's profile when a User object is saved.
    - Creates a Profile for a new User.
    - Assigns the 'admin' role to any user who is a superuser.
    """
    # The 'created' flag is True only when a new User instance is created.
    if created:
        Profile.objects.create(user=instance)
    
    # Ensure the profile is in sync, especially for superusers.
    if instance.is_superuser and instance.profile.role != 'admin':
        instance.profile.role = 'admin'
        instance.profile.save()

class Threshold(models.Model):
    """
    Defines the thresholds for low stock and expiry alerts.
    """
    low_stock_threshold = models.PositiveIntegerField(default=10, help_text="Quantity at or below which a medicine is considered low stock.")
    expiry_threshold_days = models.PositiveIntegerField(default=30, help_text="Number of days within which a medicine is considered 'expiring soon'.")
    
    class Meta:
        verbose_name_plural = "Thresholds"

    def __str__(self):
        return f"Thresholds (Low Stock: {self.low_stock_threshold}, Expiry: {self.expiry_threshold_days} days)"

class Medicine(models.Model):
    """
    Represents a medicine in the inventory.
    """
    CATEGORY_CHOICES = [
        ('Painkillers', 'Painkillers (Analgesics)'),
        ('Antibiotics', 'Antibiotics'),
        ('Antipyretics', 'Antipyretics (fever reducers)'),
        ('Antihistamines', 'Antihistamines (allergy)'),
        ('Antacids', 'Antacids (gastric)'),
        ('Antidiabetics', 'Antidiabetics'),
        ('Antihypertensives', 'Antihypertensives'),
        ('Cough & Cold', 'Cough & Cold'),
        ('Antiseptics', 'Antiseptics'),
        ('Vitamins & Supplements', 'Vitamins & Supplements'),
        ('Other', 'Other'),
    ]

    code = models.CharField(max_length=50, blank=True, verbose_name="Code")
    name = models.CharField(max_length=100, verbose_name="Name")
    brand_name = models.CharField(max_length=100, blank=True, verbose_name="Brand")
    
    category = models.CharField(max_length=50, choices=CATEGORY_CHOICES, default='Other', verbose_name="Category")
    unit_per_package = models.PositiveIntegerField(default=1, verbose_name="Units/Pkg")
    package_type = models.CharField(max_length=50, blank=True, verbose_name="Package Type")

    quantity = models.PositiveIntegerField(default=0, verbose_name="Stock Quantity")
    purchase_price = models.IntegerField(default=0, verbose_name="Buy Price")
    selling_price = models.IntegerField(default=0, verbose_name="Sell Price")
    
    purchase_date = models.DateField(null=True, blank=True, verbose_name="Buy Date")
    expiry_date = models.DateField(verbose_name="Expire Date")
    added_date = models.DateTimeField(auto_now_add=True)
    
    description = models.TextField(blank=True)
    dosage_form = models.CharField(max_length=100, blank=True)
    supplier_name = models.CharField(max_length=100, blank=True)
    storage_info = models.TextField(blank=True)
    location = models.CharField(max_length=100, blank=True)

    def __str__(self):
        return f"{self.name} ({self.brand_name})"
        
    class Meta:
        ordering = ['name']

class Sale(models.Model):
    """
    Represents a single sales transaction.
    """
    created_at = models.DateTimeField(default=timezone.now)
    created_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True, related_name='sales')
    delivery_fee = models.IntegerField(default=0)
    total_amount = models.IntegerField(default=0)
    customer_name = models.CharField(max_length=100, blank=True)
    customer_phone = models.CharField(max_length=20, blank=True)
    customer_address = models.TextField(blank=True)

    @property
    def items_only_total(self):
        """Calculates the total cost of items without the delivery fee."""
        return self.total_amount - self.delivery_fee

    def __str__(self):
        return f"Sale #{self.pk}"

    def update_total(self):
        """Recalculates and saves the total amount for the sale."""
        items_total = sum(item.subtotal for item in self.items.all())
        self.total_amount = items_total + self.delivery_fee
        self.save()

class SaleItem(models.Model):
    """
    Represents an item within a sale.
    """
    sale = models.ForeignKey(Sale, related_name='items', on_delete=models.CASCADE)
    medicine = models.ForeignKey(Medicine, on_delete=models.PROTECT) # PROTECT prevents deleting a medicine if it has been sold
    quantity = models.PositiveIntegerField()
    price_at_sale = models.IntegerField()

    @property
    def subtotal(self):
        """Calculates the subtotal for this sale item."""
        return self.quantity * self.price_at_sale

    def __str__(self):
        return f"{self.quantity} x {self.medicine.name}"

class PharmacyInfo(models.Model):
    """
    Stores basic information about the pharmacy.
    """
    name = models.CharField(max_length=200, default="NC Pharmacy")
    address = models.TextField(default="123 Main Street, Anytown, USA 12345")
    phone_number = models.CharField(max_length=20, default="(123) 456-7890")
    phone_number_2 = models.CharField(max_length=20, blank=True, null=True, help_text="Optional second phone number.")


    class Meta:
        verbose_name_plural = "Pharmacy Info"

    def __str__(self):
        return self.name
