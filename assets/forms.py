from django import forms
from .models import AssetType, Asset, Employee

class AssetTypeForm(forms.ModelForm):
    class Meta:
        model = AssetType
        fields = ['name', 'identification_type_label', 'object_description']
        widgets = {
            'name': forms.TextInput(attrs={'class': 'mt-1 block w-full px-3 py-2 border border-gray-300 rounded-md shadow-sm focus:outline-none focus:ring-indigo-500 focus:border-indigo-500'}),
            'identification_type_label': forms.TextInput(attrs={'class': 'mt-1 block w-full px-3 py-2 border border-gray-300 rounded-md shadow-sm focus:outline-none focus:ring-indigo-500 focus:border-indigo-500'}),
            'object_description': forms.TextInput(attrs={'class': 'mt-1 block w-full px-3 py-2 border border-gray-300 rounded-md shadow-sm focus:outline-none focus:ring-indigo-500 focus:border-indigo-500'}),
        }

class AssetAssignmentForm(forms.ModelForm):
    class Meta:
        model = Asset
        fields = ['asset_type', 'asset_name', 'unique_identifier', 'details']
        widgets = {
            'asset_type': forms.Select(attrs={'class': 'mt-1 block w-full px-3 py-2 border border-gray-300 rounded-md shadow-sm focus:outline-none focus:ring-indigo-500 focus:border-indigo-500', 'id': 'id_asset_type'}),
            'asset_name': forms.TextInput(attrs={'class': 'mt-1 block w-full px-3 py-2 border border-gray-300 rounded-md shadow-sm focus:outline-none focus:ring-indigo-500 focus:border-indigo-500'}),
            'unique_identifier': forms.TextInput(attrs={'class': 'mt-1 block w-full px-3 py-2 border border-gray-300 rounded-md shadow-sm focus:outline-none focus:ring-indigo-500 focus:border-indigo-500', 'id': 'id_unique_identifier', 'placeholder': 'Enter identifier (e.g., IMEI)'}),
            'details': forms.Textarea(attrs={'class': 'mt-1 block w-full px-3 py-2 border border-gray-300 rounded-md shadow-sm focus:outline-none focus:ring-indigo-500 focus:border-indigo-500', 'rows': 3}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['asset_type'].empty_label = 'Select Asset Type'

    def save(self, commit=True):
        instance = super().save(commit=False)
        instance.assigned_to = None  # Unassigned by default
        if commit:
            instance.save()
        return instance

class AssetAssignmentToEmployeeForm(forms.Form):
    asset_id = forms.ModelChoiceField(
        queryset=Asset.objects.filter(assigned_to__isnull=True),
        empty_label="Select an unassigned asset",
        widget=forms.Select(attrs={'class': 'mt-1 block w-full px-3 py-2 border border-gray-300 rounded-md shadow-sm focus:outline-none focus:ring-indigo-500 focus:border-indigo-500'})
    )
