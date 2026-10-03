from django.core.exceptions import ValidationError
from django.db import transaction

from .models import Asset, AssetType, AssignmentHistory, Employee


@transaction.atomic
def change_asset_assignment(asset_id, employee, actor=None, *, expected_employee_id):
    """Apply a checked assignment transition and record it atomically."""
    if expected_employee_id is not None:
        try:
            Employee.objects.select_for_update().get(pk=expected_employee_id)
        except Employee.DoesNotExist:
            raise ValidationError('The asset assignment changed concurrently. Refresh and try again.')
    if employee is not None:
        try:
            employee = Employee.objects.select_for_update().get(pk=employee.pk, is_active=True)
        except Employee.DoesNotExist:
            raise ValidationError('Inactive employees cannot receive assets.')
    state = Asset.objects.select_for_update().filter(
        pk=asset_id, is_active=True, asset_type__is_active=True
    ).values('assigned_to_id').first()
    if state is None:
        raise ValidationError('This asset is inactive or no longer available.')
    current = state['assigned_to_id']
    if current != expected_employee_id:
        raise ValidationError('The asset assignment changed concurrently. Refresh and try again.')
    target_id = employee.pk if employee else None
    if current == target_id:
        return False

    # Compare-and-swap prevents two concurrent requests from recording a
    # transition against stale state, including on SQLite where row locks are
    # not implemented.
    changed = Asset.objects.filter(pk=asset_id, is_active=True, asset_type__is_active=True,
                                   assigned_to_id=expected_employee_id).update(assigned_to=target_id)
    if changed != 1:
        raise ValidationError('The asset assignment changed concurrently. Refresh and try again.')
    if current is not None:
        prior_employee = Employee.objects.get(pk=current)
        AssignmentHistory.objects.create(asset_id=asset_id, employee=prior_employee,
                                          action=AssignmentHistory.Action.RETURNED, actor=actor)
    if employee is not None:
        AssignmentHistory.objects.create(
            asset_id=asset_id,
            employee=employee,
            action=AssignmentHistory.Action.ASSIGNED,
            actor=actor,
        )
    return True


def return_employee_assets(employee, actor=None):
    for asset_id, current_employee_id in Asset.objects.filter(assigned_to=employee, is_active=True).values_list('pk', 'assigned_to_id'):
        change_asset_assignment(asset_id, None, actor, expected_employee_id=current_employee_id)


@transaction.atomic
def deactivate_employee(employee_id, actor=None, exit_date=None):
    """Return current assets and deactivate an employee as one transaction."""
    employee = Employee.objects.select_for_update().get(pk=employee_id)
    if not employee.is_active:
        return employee
    return_employee_assets(employee, actor)
    employee.is_active = False
    if exit_date is not None:
        employee.exit_date = exit_date
        employee.save(update_fields=['is_active', 'exit_date'])
    else:
        employee.save(update_fields=['is_active'])
    return employee


@transaction.atomic
def deactivate_asset(asset_id, actor=None, *, expected_employee_id):
    asset = Asset.objects.select_for_update().get(pk=asset_id)
    if asset.assigned_to_id != expected_employee_id:
        raise ValidationError('The asset assignment changed concurrently. Refresh and try again.')
    if asset.assigned_to_id is not None:
        change_asset_assignment(asset.pk, None, actor, expected_employee_id=asset.assigned_to_id)
    asset.is_active = False
    asset.save(update_fields=['is_active'])
    return asset
