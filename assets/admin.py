from django.contrib import admin
from django.contrib.auth import get_user_model
from django.contrib.auth.admin import UserAdmin

from .models import Asset, AssetType, AssignmentHistory, AssetExceptionCase, Employee


class StaffOnlyAdminSite(admin.AdminSite):
    site_header = 'Asset operations administration'

    def has_permission(self, request):
        return bool(request.user.is_active and request.user.is_superuser)


staff_admin_site = StaffOnlyAdminSite(name='staff_admin')


class NoDeleteAdmin(admin.ModelAdmin):
    def has_add_permission(self, request):
        return False

    def has_change_permission(self, request, obj=None):
        return False

    def has_delete_permission(self, request, obj=None):
        return False


class ManagedUserAdmin(UserAdmin):
    def has_delete_permission(self, request, obj=None):
        return False


staff_admin_site.register(get_user_model(), ManagedUserAdmin)


@admin.register(Employee, site=staff_admin_site)
class EmployeeAdmin(NoDeleteAdmin):
    list_display = ('employee_id', 'name', 'department', 'is_active')
    search_fields = ('employee_id', 'name', 'department')


@admin.register(AssetType, site=staff_admin_site)
class AssetTypeAdmin(NoDeleteAdmin):
    list_display = ('name', 'is_active')


@admin.register(Asset, site=staff_admin_site)
class AssetAdmin(NoDeleteAdmin):
    list_display = ('asset_name', 'unique_identifier', 'asset_type', 'assigned_to', 'disposition', 'is_active')
    readonly_fields = ('assigned_to', 'disposition', 'is_active')


@admin.register(AssignmentHistory, site=staff_admin_site)
class AssignmentHistoryAdmin(admin.ModelAdmin):
    list_display = ('asset', 'employee', 'action', 'occurred_at', 'actor')
    readonly_fields = ('asset', 'employee', 'action', 'occurred_at', 'observed_at', 'actor',
                       'receipt_condition', 'note', 'source', 'case')
    def has_add_permission(self, request):
        return False
    def has_change_permission(self, request, obj=None):
        return False
    def has_delete_permission(self, request, obj=None):
        return False


@admin.register(AssetExceptionCase, site=staff_admin_site)
class AssetExceptionCaseAdmin(NoDeleteAdmin):
    list_display = ('id', 'asset', 'kind', 'opened_at', 'resolved_at')
    readonly_fields = ('asset', 'kind', 'reason', 'opened_at', 'observed_at', 'opened_by',
                       'source', 'resolved_at', 'resolved_by', 'resolution_note')
