"""Atomic custody and condition transitions for the staff workspace."""

from django.core.exceptions import ValidationError
from django.db import transaction
from django.utils import timezone

from .models import Asset, AssetExceptionCase, AssignmentHistory, Employee


STALE = 'The asset custody or condition changed concurrently. Refresh and try again.'


def _staff_actor(actor):
    if actor is None or not actor.is_active or not actor.is_staff:
        raise ValidationError('An active staff actor is required for this action.')


def _lock_employee(employee_id, *, must_be_active=False):
    try:
        employee = Employee.objects.select_for_update().get(pk=employee_id)
    except Employee.DoesNotExist:
        raise ValidationError(STALE)
    if must_be_active and not employee.is_active:
        raise ValidationError('Inactive employees cannot receive assets.')
    return employee


def _lock_asset(asset_id, expected_employee_id, expected_disposition):
    try:
        asset = Asset.objects.select_for_update().get(
            pk=asset_id, is_active=True, asset_type__is_active=True,
        )
    except Asset.DoesNotExist:
        raise ValidationError('This asset is inactive or its category is unavailable.')
    if asset.assigned_to_id != expected_employee_id or asset.disposition != expected_disposition:
        raise ValidationError(STALE)
    return asset


def _current_case(asset):
    return AssetExceptionCase.objects.select_for_update().filter(
        asset=asset, resolved_at__isnull=True,
    ).first()


def _open_case(asset, kind, reason, actor, source, observed_at=None):
    return AssetExceptionCase.objects.create(
        asset=asset, kind=kind, reason=reason, opened_by=actor, source=source,
        observed_at=observed_at,
    )


def _event(asset, employee, action, actor, *, case=None, note='',
           source=AssignmentHistory.Source.STAFF, observed_at=None, receipt_condition=''):
    return AssignmentHistory.objects.create(
        asset=asset, employee=employee, action=action, actor=actor, case=case,
        note=note, source=source, observed_at=observed_at,
        receipt_condition=receipt_condition,
    )


@transaction.atomic
def change_asset_assignment(asset_id, employee, actor=None, *, expected_employee_id):
    """Assign only a ready asset; a physical return is a separate explicit action."""
    _staff_actor(actor)
    if employee is None or expected_employee_id is not None:
        raise ValidationError('Return the asset with a physical receipt before assigning it.')
    employee = _lock_employee(employee.pk, must_be_active=True)
    asset = _lock_asset(asset_id, None, Asset.Disposition.READY)
    if _current_case(asset):
        raise ValidationError('Resolve the open asset exception before assigning it.')
    changed = Asset.objects.filter(
        pk=asset_id, is_active=True, asset_type__is_active=True,
        assigned_to__isnull=True, disposition=Asset.Disposition.READY,
    ).update(assigned_to=employee, disposition=Asset.Disposition.ASSIGNED)
    if changed != 1:
        raise ValidationError(STALE)
    _event(asset, employee, AssignmentHistory.Action.ASSIGNED, actor)
    return True


@transaction.atomic
def record_physical_receipt(asset_id, actor, *, expected_employee_id,
                            expected_disposition, condition, note='', observed_at=None):
    _staff_actor(actor)
    if condition not in AssignmentHistory.ReceiptCondition.values:
        raise ValidationError('Choose whether the received asset is usable or damaged.')
    note = note.strip()
    if condition == AssignmentHistory.ReceiptCondition.DAMAGED and not note:
        raise ValidationError('Describe the damage before recording receipt.')
    if expected_disposition in (Asset.Disposition.RECOVERY_PENDING, Asset.Disposition.MISSING) and not note:
        raise ValidationError('Record how the outstanding asset was recovered.')
    if expected_employee_id is None:
        raise ValidationError(STALE)
    employee = _lock_employee(expected_employee_id)
    asset = _lock_asset(asset_id, expected_employee_id, expected_disposition)
    if asset.disposition not in (Asset.Disposition.ASSIGNED, Asset.Disposition.RECOVERY_PENDING,
                                 Asset.Disposition.MISSING):
        raise ValidationError('This asset is not awaiting physical receipt.')
    case = _current_case(asset)
    if asset.disposition != Asset.Disposition.ASSIGNED and case is None:
        raise ValidationError('The outstanding custody case is missing; ask an administrator to review it.')
    if asset.disposition == Asset.Disposition.ASSIGNED and case is not None:
        raise ValidationError('The asset has an unexpected open case; ask an administrator to review it.')
    next_state = (Asset.Disposition.READY if condition == AssignmentHistory.ReceiptCondition.USABLE
                  else Asset.Disposition.INSPECTION_HOLD)
    changed = Asset.objects.filter(
        pk=asset_id, is_active=True, assigned_to_id=expected_employee_id,
        disposition=expected_disposition,
    ).update(assigned_to=None, disposition=next_state)
    if changed != 1:
        raise ValidationError(STALE)
    if condition == AssignmentHistory.ReceiptCondition.DAMAGED:
        if case is None:
            case = _open_case(asset, AssetExceptionCase.Kind.INSPECTION, note, actor,
                              AssignmentHistory.Source.STAFF, observed_at)
        else:
            case.kind = AssetExceptionCase.Kind.INSPECTION
            case.save(update_fields=['kind'])
    elif case is not None:
        case.resolved_at = timezone.now()
        case.resolved_by = actor
        case.resolution_note = note
        case.save(update_fields=['resolved_at', 'resolved_by', 'resolution_note'])
    _event(asset, employee, AssignmentHistory.Action.RETURNED, actor, case=case,
           note=note, observed_at=observed_at, receipt_condition=condition)
    return next_state


@transaction.atomic
def report_missing(asset_id, actor, *, expected_employee_id, expected_disposition,
                   note, observed_at=None):
    _staff_actor(actor)
    note = note.strip()
    if not note:
        raise ValidationError('Describe why the asset is reported missing or unreceived.')
    if expected_employee_id is None:
        raise ValidationError(STALE)
    employee = _lock_employee(expected_employee_id)
    asset = _lock_asset(asset_id, expected_employee_id, expected_disposition)
    if asset.disposition not in (Asset.Disposition.ASSIGNED, Asset.Disposition.RECOVERY_PENDING):
        raise ValidationError('Only held assets can be reported missing.')
    case = _current_case(asset)
    if asset.disposition == Asset.Disposition.RECOVERY_PENDING and case is None:
        raise ValidationError('The outstanding custody case is missing; ask an administrator to review it.')
    if asset.disposition == Asset.Disposition.ASSIGNED and case is not None:
        raise ValidationError('The asset has an unexpected open case; ask an administrator to review it.')
    changed = Asset.objects.filter(
        pk=asset_id, is_active=True, assigned_to_id=expected_employee_id,
        disposition=expected_disposition,
    ).update(disposition=Asset.Disposition.MISSING)
    if changed != 1:
        raise ValidationError(STALE)
    if case is None:
        case = _open_case(asset, AssetExceptionCase.Kind.MISSING, note, actor,
                          AssignmentHistory.Source.STAFF, observed_at)
    else:
        case.kind = AssetExceptionCase.Kind.MISSING
        case.save(update_fields=['kind'])
    _event(asset, employee, AssignmentHistory.Action.MISSING_REPORTED, actor,
           case=case, note=note, observed_at=observed_at)
    return case


@transaction.atomic
def release_inspection(asset_id, actor, *, note):
    _staff_actor(actor)
    note = note.strip()
    if not note:
        raise ValidationError('Record the inspection result before releasing this asset.')
    asset = _lock_asset(asset_id, None, Asset.Disposition.INSPECTION_HOLD)
    case = _current_case(asset)
    if case is None or case.kind != AssetExceptionCase.Kind.INSPECTION:
        raise ValidationError('The inspection case is missing; ask an administrator to review it.')
    changed = Asset.objects.filter(
        pk=asset_id, is_active=True, assigned_to__isnull=True,
        disposition=Asset.Disposition.INSPECTION_HOLD,
    ).update(disposition=Asset.Disposition.READY)
    if changed != 1:
        raise ValidationError(STALE)
    case.resolved_at = timezone.now()
    case.resolved_by = actor
    case.resolution_note = note
    case.save(update_fields=['resolved_at', 'resolved_by', 'resolution_note'])
    _event(asset, None, AssignmentHistory.Action.INSPECTION_RELEASED, actor,
           case=case, note=note)
    return asset


@transaction.atomic
def deactivate_employee(employee_id, actor=None, exit_date=None):
    """Deactivate a profile while preserving unconfirmed physical custody."""
    if actor is not None:
        _staff_actor(actor)
    employee = _lock_employee(employee_id)
    if not employee.is_active:
        return employee
    source = AssignmentHistory.Source.STAFF if actor else AssignmentHistory.Source.SCHEDULED
    reason = 'Employee deactivated with physical asset receipt still unconfirmed.'
    for asset in Asset.objects.select_for_update().filter(
            assigned_to=employee, is_active=True).order_by('pk'):
        if asset.disposition == Asset.Disposition.ASSIGNED:
            if _current_case(asset):
                raise ValidationError('The asset has an unexpected open case; ask an administrator to review it.')
            changed = Asset.objects.filter(
                pk=asset.pk, assigned_to=employee, disposition=Asset.Disposition.ASSIGNED,
            ).update(disposition=Asset.Disposition.RECOVERY_PENDING)
            if changed != 1:
                raise ValidationError(STALE)
            case = _open_case(asset, AssetExceptionCase.Kind.RECOVERY, reason, actor, source)
            _event(asset, employee, AssignmentHistory.Action.RECOVERY_PENDING, actor,
                   case=case, note=reason, source=source)
        elif asset.disposition in (Asset.Disposition.RECOVERY_PENDING, Asset.Disposition.MISSING):
            if _current_case(asset) is None:
                raise ValidationError('The outstanding custody case is missing; ask an administrator to review it.')
        else:
            raise ValidationError('Resolve inconsistent asset custody before deactivating this employee.')
    employee.is_active = False
    if exit_date is not None:
        employee.exit_date = exit_date
        employee.save(update_fields=['is_active', 'exit_date'])
    else:
        employee.save(update_fields=['is_active'])
    return employee


@transaction.atomic
def deactivate_asset(asset_id, actor=None, *, expected_employee_id):
    _staff_actor(actor)
    if expected_employee_id is not None:
        raise ValidationError('Resolve current custody before retiring this asset.')
    asset = _lock_asset(asset_id, None, Asset.Disposition.READY)
    if _current_case(asset):
        raise ValidationError('Resolve the open asset exception before retirement.')
    changed = Asset.objects.filter(
        pk=asset_id, is_active=True, assigned_to__isnull=True,
        disposition=Asset.Disposition.READY,
    ).update(is_active=False)
    if changed != 1:
        raise ValidationError(STALE)
    return asset
