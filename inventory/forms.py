# inventory/forms.py

from django import forms
from django.contrib.auth.models import User
from .models import Medicine, Threshold, Profile, PharmacyInfo

class PharmacyInfoForm(forms.ModelForm):
    """Form for updating pharmacy information."""
    class Meta:
        model = PharmacyInfo
        fields = ['name', 'address', 'phone_number', 'phone_number_2']
        widgets = {
            'name': forms.TextInput(attrs={'class': 'form-control'}),
            'address': forms.Textarea(attrs={'class': 'form-control', 'rows': 3}),
            'phone_number': forms.TextInput(attrs={'class': 'form-control'}),
            'phone_number_2': forms.TextInput(attrs={'class': 'form-control'}),
        }

class StaffCreationForm(forms.ModelForm):
    """
    A form for the 'admin' to create new staff users.
    """
    password = forms.CharField(widget=forms.PasswordInput(attrs={'class': 'form-control'}), required=True)
    
    class Meta:
        model = User
        fields = ('username',)
        widgets = {
            'username': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Enter a username'}),
        }

    def save(self, commit=True):
        user = super().save(commit=False)
        user.set_password(self.cleaned_data["password"])
        if commit:
            user.save()
            # The post_save signal will create the Profile, here we just set the role.
            user.profile.role = 'staff'
            user.profile.save()
        return user

class StaffPasswordChangeForm(forms.Form):
    """
    A form for an admin to change a staff member's password.
    """
    password = forms.CharField(widget=forms.PasswordInput(attrs={'class': 'form-control'}), required=True, label="New Password")
    password_confirm = forms.CharField(widget=forms.PasswordInput(attrs={'class': 'form-control'}), required=True, label="Confirm New Password")

    def clean(self):
        """Ensures that the two password fields match."""
        cleaned_data = super().clean()
        password = cleaned_data.get("password")
        password_confirm = cleaned_data.get("password_confirm")

        if password and password_confirm and password != password_confirm:
            raise forms.ValidationError("Passwords do not match.")
        return cleaned_data

class FileUploadForm(forms.Form):
    """Form for uploading a file."""
    file = forms.FileField(label="Select a CSV or Excel file", widget=forms.FileInput(attrs={'class': 'form-control'}))

class MedicineForm(forms.ModelForm):
    """Form for creating and updating Medicine instances."""
    class Meta:
        model = Medicine
        fields = [
            'code', 'name', 'brand_name', 'category', 'unit_per_package', 
            'package_type', 'quantity', 'purchase_price', 'selling_price', 
            'purchase_date', 'expiry_date'
        ]
        widgets = {
            'code': forms.TextInput(attrs={'class': 'form-control'}),
            'name': forms.TextInput(attrs={'class': 'form-control'}),
            'brand_name': forms.TextInput(attrs={'class': 'form-control'}),
            'category': forms.Select(attrs={'class': 'form-select'}),
            'unit_per_package': forms.NumberInput(attrs={'class': 'form-control'}),
            'package_type': forms.TextInput(attrs={'class': 'form-control'}),
            'quantity': forms.NumberInput(attrs={'class': 'form-control'}),
            'purchase_price': forms.NumberInput(attrs={'class': 'form-control'}),
            'selling_price': forms.NumberInput(attrs={'class': 'form-control'}),
            'purchase_date': forms.DateInput(attrs={'type': 'date', 'class': 'form-control'}),
            'expiry_date': forms.DateInput(attrs={'type': 'date', 'class': 'form-control'}),
        }

class ThresholdForm(forms.ModelForm):
    """Form for updating Threshold settings."""
    class Meta:
        model = Threshold
        fields = ['low_stock_threshold', 'expiry_threshold_days']
        widgets = {
            'low_stock_threshold': forms.NumberInput(attrs={'class': 'form-control'}),
            'expiry_threshold_days': forms.NumberInput(attrs={'class': 'form-control'}),
        }
