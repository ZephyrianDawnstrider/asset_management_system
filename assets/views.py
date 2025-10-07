from django.shortcuts import render, get_object_or_404, redirect
from django.views.generic import ListView, CreateView, UpdateView, DeleteView, DetailView, TemplateView
from django.urls import reverse_lazy
from django.contrib.auth.mixins import LoginRequiredMixin, UserPassesTestMixin
from .models import Employee, AssetType, Asset
from .forms import AssetAssignmentForm, AssetAssignmentToEmployeeForm
from django.http import JsonResponse
from django.views import View
from django.views.decorators.csrf import csrf_exempt
from django.utils.decorators import method_decorator

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
        if employee.exit_date:
            from django.utils import timezone
            if employee.exit_date <= timezone.now().date():
                # Past or present: soft delete immediately
                employee.is_active = False
                # Unassign all assets
                Asset.objects.filter(assigned_to=employee).update(assigned_to=None)
        # For future dates, just save; daily command will handle soft delete
        employee.save()
        return super().form_valid(form)

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

class AssetSoftDeleteView(LoginRequiredMixin, UserPassesTestMixin, View):
    def test_func(self):
        return self.request.user.is_staff

    def post(self, request, pk):
        asset = get_object_or_404(Asset, pk=pk)
        if asset.is_active:
            asset.is_active = False
            asset.save()
        return redirect('asset_list')

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
        return Employee.objects.filter(is_active=True)

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
            row = [employee]
            for asset_type in asset_types:
                has = employee.employee_id in assignment_lookup and asset_type.id in assignment_lookup.get(employee.employee_id, set())
                row.append(has)
            employee_rows.append(row)
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
            # Soft delete: set inactive and unassign assets
            employee.is_active = False
            employee.save()
            Asset.objects.filter(assigned_to=employee).update(assigned_to=None)
        return redirect('employee_list')

class EmployeeDeleteView(LoginRequiredMixin, UserPassesTestMixin, DeleteView):
    model = Employee
    template_name = 'assets/employee_confirm_delete.html'
    success_url = reverse_lazy('employee_overview')
    slug_field = 'employee_id'
    slug_url_kwarg = 'employee_id'

    def test_func(self):
        return self.request.user.is_staff

    def delete(self, request, *args, **kwargs):
        employee = self.get_object()
        # Unassign all assets
        Asset.objects.filter(assigned_to=employee).update(assigned_to=None)
        # Delete employee
        response = super().delete(request, *args, **kwargs)
        return response

@method_decorator(csrf_exempt, name='dispatch')
class AssignAssetToEmployeeView(LoginRequiredMixin, UserPassesTestMixin, View):
    def test_func(self):
        return self.request.user.is_staff

    def post(self, request):
        employee_id = request.POST.get('employee_id')
        asset_id = request.POST.get('asset_id')
        if employee_id and asset_id:
            employee = get_object_or_404(Employee, employee_id=employee_id, is_active=True)
            asset = get_object_or_404(Asset, id=asset_id)
            if asset.assigned_to is None:
                asset.assigned_to = employee
                asset.save()
                return JsonResponse({'success': True, 'message': 'Asset assigned successfully'})
        return JsonResponse({'success': False, 'message': 'Invalid request'})

class UnassignAssetView(LoginRequiredMixin, UserPassesTestMixin, View):
    def test_func(self):
        return self.request.user.is_staff

    def post(self, request, asset_id):
        asset = get_object_or_404(Asset, id=asset_id)
        if asset.assigned_to:
            asset.assigned_to = None
            asset.save()
            return JsonResponse({'success': True, 'message': 'Asset unassigned successfully'})
        return JsonResponse({'success': False, 'message': 'Asset is not assigned'})

class UnassignedAssetsAPIView(View):
    def get(self, request, asset_type_id):
        unassigned = Asset.objects.filter(asset_type_id=asset_type_id, assigned_to__isnull=True, is_active=True).values('id', 'asset_name', 'unique_identifier')
        return JsonResponse(list(unassigned), safe=False)
