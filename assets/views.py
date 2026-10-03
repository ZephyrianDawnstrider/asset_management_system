import csv

from django.shortcuts import render, get_object_or_404, redirect
from django.views.generic import ListView, CreateView, UpdateView, DeleteView, DetailView, TemplateView
from django.urls import reverse_lazy
from django.contrib.auth.mixins import LoginRequiredMixin, UserPassesTestMixin
from django.contrib import messages
from django.core.exceptions import ValidationError
from django.db import transaction
from django.http import JsonResponse, HttpResponse
from django.utils import timezone
from .models import Employee, AssetType, Asset, AssignmentHistory
from .forms import AssetAssignmentForm, AssetAssignmentToEmployeeForm
from django.views import View
from .services import change_asset_assignment, deactivate_asset, deactivate_employee


class HomeView(TemplateView):
    template_name = 'assets/landing.html'

    def get(self, request, *args, **kwargs):
        if request.user.is_authenticated:
            if request.user.is_staff:
                return redirect('employee_overview')
            else:
                # For regular users, perhaps a different dashboard or logout
                return redirect('account_logout')
        else:
            # Show landing page for unauthenticated users
            return super().get(request, *args, **kwargs)

# Employee CRUD Views
class EmployeeListView(LoginRequiredMixin, UserPassesTestMixin, ListView):
    model = Employee
    template_name = 'assets/employee_list.html'
    context_object_name = 'employees'

    def test_func(self):
        return self.request.user.is_staff

    def get_queryset(self):
        return Employee.objects.filter(is_active=True)

class EmployeeCreateView(LoginRequiredMixin, UserPassesTestMixin, CreateView):
    model = Employee
    template_name = 'assets/employee_form.html'
    fields = ['employee_id', 'name', 'department', 'designation', 'start_date']
    success_url = reverse_lazy('employee_list')

    def test_func(self):
        return self.request.user.is_staff

    def get_form(self, form_class=None):
        form = super().get_form(form_class)
        form.fields['start_date'].widget.attrs.update({'type': 'date'})
        return form

    def form_valid(self, form):
        employee_id = form.cleaned_data['employee_id']
        existing_employee = Employee.objects.filter(employee_id=employee_id).first()
        if existing_employee:
            if not existing_employee.is_active:
                # Reactivate and update
                existing_employee.name = form.cleaned_data['name']
                existing_employee.department = form.cleaned_data['department']
                existing_employee.designation = form.cleaned_data['designation']
                existing_employee.start_date = form.cleaned_data['start_date']
                existing_employee.is_active = True
                existing_employee.save()
                return redirect(self.success_url)
            else:
                # Already active, perhaps error or update
                form.add_error('employee_id', 'Employee with this ID already exists and is active.')
                return self.form_invalid(form)
        return super().form_valid(form)

class EmployeeUpdateView(LoginRequiredMixin, UserPassesTestMixin, UpdateView):
    model = Employee
    template_name = 'assets/employee_form.html'
    fields = ['employee_id', 'name', 'department', 'designation', 'start_date', 'exit_date']
    success_url = reverse_lazy('employee_list')

    def test_func(self):
        return self.request.user.is_staff

    def get_form(self, form_class=None):
        form = super().get_form(form_class)
        form.fields['start_date'].widget.attrs.update({'type': 'date'})
        form.fields['exit_date'].widget.attrs.update({'type': 'date'})
        return form

    def form_valid(self, form):
        employee = form.save(commit=False)
        editable_fields = ['employee_id', 'name', 'department', 'designation', 'start_date', 'exit_date']
        if employee.exit_date:
            if employee.exit_date <= timezone.now().date():
                with transaction.atomic():
                    employee.save(update_fields=editable_fields)
                    deactivate_employee(employee.pk, self.request.user, employee.exit_date)
                return redirect(self.success_url)
        employee.save(update_fields=editable_fields)
        return redirect(self.success_url)

# AssetType CRUD Views
class AssetTypeListView(LoginRequiredMixin, UserPassesTestMixin, ListView):
    model = AssetType
    template_name = 'assets/assettype_list.html'
    context_object_name = 'asset_types'

    def test_func(self):
        return self.request.user.is_staff

    def get_queryset(self):
        return AssetType.objects.filter(is_active=True)

class AssetTypeCreateView(LoginRequiredMixin, UserPassesTestMixin, CreateView):
    model = AssetType
    template_name = 'assets/assettype_form.html'
    fields = ['name', 'identification_type_label', 'object_description']
    success_url = reverse_lazy('assettype_list')

    def test_func(self):
        return self.request.user.is_staff

class AssetTypeUpdateView(LoginRequiredMixin, UserPassesTestMixin, UpdateView):
    model = AssetType
    template_name = 'assets/assettype_form.html'
    fields = ['name', 'identification_type_label', 'object_description']
    success_url = reverse_lazy('assettype_list')

    def test_func(self):
        return self.request.user.is_staff

class AssetTypeSoftDeleteView(LoginRequiredMixin, UserPassesTestMixin, View):
    def test_func(self):
        return self.request.user.is_staff

    def post(self, request, pk):
        asset_type = get_object_or_404(AssetType, pk=pk)
        if asset_type.is_active:
            if Asset.objects.filter(asset_type=asset_type, is_active=True).exists():
                messages.error(request, 'Return and deactivate every asset of this type before deactivating the type.')
                return redirect('assettype_list')
            asset_type.is_active = False
            asset_type.save()
        return redirect('assettype_list')

class AssetListView(LoginRequiredMixin, UserPassesTestMixin, ListView):
    model = Asset
    template_name = 'assets/asset_list.html'
    context_object_name = 'assets'

    def test_func(self):
        return self.request.user.is_staff

    def get_queryset(self):
        return Asset.objects.filter(is_active=True).select_related('asset_type', 'assigned_to')

class AssetUpdateView(LoginRequiredMixin, UserPassesTestMixin, UpdateView):
    model = Asset
    template_name = 'assets/asset_form.html'
    fields = ['asset_type', 'asset_name', 'unique_identifier', 'details']
    success_url = reverse_lazy('asset_assign')

    def test_func(self):
        return self.request.user.is_staff

    def get_form(self, form_class=None):
        form = super().get_form(form_class)
        form.fields['asset_type'].queryset = AssetType.objects.filter(is_active=True)
        if self.object.assigned_to_id:
            form.fields['asset_type'].disabled = True
        return form

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['asset_types'] = AssetType.objects.filter(is_active=True)
        context['employees'] = Employee.objects.filter(is_active=True)
        return context

class AssetSoftDeleteView(LoginRequiredMixin, UserPassesTestMixin, View):
    def test_func(self):
        return self.request.user.is_staff

    def post(self, request, pk):
        asset = get_object_or_404(Asset, pk=pk)
        if asset.is_active:
            if asset.assigned_to_id:
                try:
                    expected_employee_id = int(request.POST.get('expected_employee_id', ''))
                except (TypeError, ValueError):
                    return JsonResponse({'success': False, 'message': 'Refresh this page before deactivating the asset.'}, status=400)
            else:
                expected_employee_id = None
            try:
                deactivate_asset(asset.pk, request.user, expected_employee_id=expected_employee_id)
            except ValidationError as exc:
                return JsonResponse({'success': False, 'message': exc.messages[0]}, status=409)
        return redirect('asset_assign')

# Asset Assignment View
class AssetAssignmentView(LoginRequiredMixin, UserPassesTestMixin, CreateView):
    model = Asset
    form_class = AssetAssignmentForm
    template_name = 'assets/asset_assignment_form.html'
    success_url = reverse_lazy('asset_assign')

    def test_func(self):
        return self.request.user.is_staff

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['asset_types'] = AssetType.objects.filter(is_active=True)
        context['all_assets'] = Asset.objects.filter(is_active=True).select_related('asset_type', 'assigned_to')
        return context

# Employee Overview (Tickmark Matrix)
class EmployeeAssetOverviewView(LoginRequiredMixin, UserPassesTestMixin, ListView):
    model = Employee
    template_name = 'assets/employee_overview.html'
    context_object_name = 'employees'

    def test_func(self):
        return self.request.user.is_staff

    def get_queryset(self):
        return Employee.objects.filter(is_active=True).order_by('employee_id')

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        asset_types = AssetType.objects.filter(is_active=True)
        # Fetch all assignments
        assignments = Asset.objects.filter(assigned_to__isnull=False, is_active=True).select_related('assigned_to', 'asset_type')
        # Create lookup: employee_id -> set of asset_type_ids
        assignment_lookup = {}
        for asset in assignments:
            emp_id = asset.assigned_to.employee_id
            if emp_id not in assignment_lookup:
                assignment_lookup[emp_id] = set()
            assignment_lookup[emp_id].add(asset.asset_type.id)
        context['asset_types'] = asset_types
        # Create matrix
        employee_rows = []
        for employee in context['employees']:
            row_assets = [
                {'asset_type': asset_type,
                 'assigned': asset_type.id in assignment_lookup.get(employee.employee_id, set())}
                for asset_type in asset_types
            ]
            employee_rows.append({'employee': employee, 'assets': row_assets})
        context['employee_rows'] = employee_rows
        return context

# Employee Detail
class EmployeeAssetDetailView(LoginRequiredMixin, UserPassesTestMixin, DetailView):
    model = Employee
    template_name = 'assets/employee_detail.html'
    context_object_name = 'employee'
    slug_field = 'employee_id'
    slug_url_kwarg = 'employee_id'

    def test_func(self):
        return self.request.user.is_staff

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        employee = self.get_object()
        assigned_assets = Asset.objects.filter(assigned_to=employee, is_active=True).select_related('asset_type')
        context['assigned_assets'] = assigned_assets
        context['assignment_history'] = AssignmentHistory.objects.filter(employee=employee).select_related('asset', 'actor')
        context['available_assets'] = Asset.objects.filter(
            is_active=True, assigned_to__isnull=True, asset_type__is_active=True
        ).select_related('asset_type').order_by('asset_type__name', 'asset_name')

        # Unassigned assets by type for assignment
        asset_types = AssetType.objects.filter(is_active=True)
        unassigned_by_type = {}
        for at in asset_types:
            unassigned = Asset.objects.filter(asset_type=at, assigned_to__isnull=True, is_active=True).order_by('asset_name')
            unassigned_by_type[at.id] = unassigned
        context['unassigned_by_type'] = unassigned_by_type
        context['asset_types'] = asset_types

        # Check if employee has asset of each type
        assigned_types = set(assigned_assets.values_list('asset_type__id', flat=True))
        context['assigned_types'] = assigned_types

        return context

class EmployeeSoftDeleteView(LoginRequiredMixin, UserPassesTestMixin, View):
    def test_func(self):
        return self.request.user.is_staff

    def post(self, request, employee_id):
        employee = get_object_or_404(Employee, employee_id=employee_id)
        if employee.is_active:
            deactivate_employee(employee.pk, request.user)
        return redirect('employee_list')

class EmployeeDeleteView(LoginRequiredMixin, UserPassesTestMixin, DeleteView):
    model = Employee
    template_name = 'assets/employee_confirm_delete.html'
    success_url = reverse_lazy('employee_overview')
    slug_field = 'employee_id'
    slug_url_kwarg = 'employee_id'

    def test_func(self):
        return self.request.user.is_staff

    def post(self, request, *args, **kwargs):
        employee = self.get_object()
        deactivate_employee(employee.pk, request.user, employee.exit_date or timezone.now().date())
        messages.success(request, 'Employee deactivated; assignment history was retained.')
        return redirect(self.success_url)

class AssignAssetToEmployeeView(LoginRequiredMixin, UserPassesTestMixin, View):
    def test_func(self):
        return self.request.user.is_staff

    def post(self, request):
        employee_id = request.POST.get('employee_id')
        asset_id = request.POST.get('asset_id')
        if employee_id and asset_id:
            employee = get_object_or_404(Employee, employee_id=employee_id, is_active=True)
            asset = get_object_or_404(Asset, id=asset_id, is_active=True)
            try:
                changed = change_asset_assignment(asset.pk, employee, request.user, expected_employee_id=None)
            except ValidationError as exc:
                return JsonResponse({'success': False, 'message': exc.messages[0]}, status=409 if 'concurrently' in exc.messages[0] else 400)
            return JsonResponse({'success': True, 'message': 'Asset assigned successfully' if changed else 'Asset is already assigned to this employee'})
        return JsonResponse({'success': False, 'message': 'Invalid request'})

class UnassignAssetView(LoginRequiredMixin, UserPassesTestMixin, View):
    def test_func(self):
        return self.request.user.is_staff

    def post(self, request, asset_id):
        asset = get_object_or_404(Asset, id=asset_id, is_active=True)
        if asset.assigned_to:
            try:
                expected_employee_id = int(request.POST.get('expected_employee_id', ''))
            except (TypeError, ValueError):
                return JsonResponse({'success': False, 'message': 'Refresh this page before returning the asset.'}, status=400)
            try:
                change_asset_assignment(asset.pk, None, request.user, expected_employee_id=expected_employee_id)
            except ValidationError as exc:
                return JsonResponse({'success': False, 'message': exc.messages[0]}, status=409)
            return JsonResponse({'success': True, 'message': 'Asset returned successfully'})
        return JsonResponse({'success': False, 'message': 'Asset is not assigned'})

class UnassignedAssetsAPIView(LoginRequiredMixin, UserPassesTestMixin, View):
    def test_func(self):
        return self.request.user.is_staff

    def get(self, request, asset_type_id):
        if not AssetType.objects.filter(pk=asset_type_id, is_active=True).exists():
            return JsonResponse({'detail': 'Asset type is unavailable.'}, status=404)
        unassigned = Asset.objects.filter(asset_type_id=asset_type_id, assigned_to__isnull=True, is_active=True).values('id', 'asset_name', 'unique_identifier')
        return JsonResponse(list(unassigned), safe=False)


class EmployeeAssetOverviewCSVView(LoginRequiredMixin, UserPassesTestMixin, View):
    def test_func(self):
        return self.request.user.is_staff

    @staticmethod
    def safe_cell(value):
        value = '' if value is None else str(value)
        if value.lstrip(' \t\r\n').startswith(('=', '+', '-', '@')):
            return "'" + value
        return value

    def get(self, request):
        response = HttpResponse(content_type='text/csv; charset=utf-8')
        response['Content-Disposition'] = 'attachment; filename="employee-asset-overview.csv"'
        writer = csv.writer(response)
        writer.writerow(['employee_id', 'employee_name', 'department', 'designation', 'asset_type', 'asset_name', 'serial_number', 'assignment_status'])
        employees = Employee.objects.filter(is_active=True).prefetch_related('asset_set__asset_type').order_by('employee_id')
        for employee in employees:
            assets = [asset for asset in employee.asset_set.all() if asset.is_active]
            rows = assets or [None]
            for asset in rows:
                writer.writerow([self.safe_cell(value) for value in (
                    employee.employee_id, employee.name, employee.department, employee.designation,
                    asset.asset_type.name if asset else '', asset.asset_name if asset else '',
                    asset.unique_identifier if asset else '', 'Assigned' if asset else 'No active assets',
                )])
        return response
