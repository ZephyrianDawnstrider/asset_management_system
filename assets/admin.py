from django.contrib import admin
from .models import Employee, AssetType, Asset

admin.site.register(Employee)
admin.site.register(AssetType)
admin.site.register(Asset)
