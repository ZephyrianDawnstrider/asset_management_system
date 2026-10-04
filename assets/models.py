from django.conf import settings
from django.db import models
from django.utils import timezone

class Employee(models.Model):
    employee_id = models.CharField(max_length=100, unique=True)
    name = models.CharField(max_length=255)
    department = models.CharField(max_length=255)
    designation = models.CharField(max_length=255)
    start_date = models.DateField()
    exit_date = models.DateField(null=True, blank=True)
    is_active = models.BooleanField(default=True)

    def __str__(self):
        return self.name

    class Meta:
        ordering = ['-start_date']

class AssetType(models.Model):
    name = models.CharField(max_length=255)
    identification_type_label = models.CharField(max_length=255)
    object_description = models.CharField(max_length=255)
    is_active = models.BooleanField(default=True)

    def __str__(self):
        return self.name

class Asset(models.Model):
    class Disposition(models.TextChoices):
        READY = 'ready', 'Ready'
        ASSIGNED = 'assigned', 'Assigned'
        RECOVERY_PENDING = 'recovery_pending', 'Recovery pending'
        MISSING = 'missing', 'Reported missing'
        INSPECTION_HOLD = 'inspection_hold', 'Inspection hold'

    asset_type = models.ForeignKey(AssetType, on_delete=models.CASCADE)
    unique_identifier = models.CharField(max_length=255, unique=True)
    asset_name = models.CharField(max_length=255)
    assigned_to = models.ForeignKey(Employee, on_delete=models.PROTECT, null=True, blank=True)
    details = models.TextField(blank=True)
    is_active = models.BooleanField(default=True)
    disposition = models.CharField(max_length=20, choices=Disposition.choices, default=Disposition.READY)

    class Meta:
        unique_together = ('asset_type', 'unique_identifier')
        constraints = [
            models.CheckConstraint(
                condition=(
                    models.Q(disposition__in=['ready', 'inspection_hold'], assigned_to__isnull=True)
                    | models.Q(disposition__in=['assigned', 'recovery_pending', 'missing'], assigned_to__isnull=False)
                ),
                name='asset_disposition_matches_holder',
            ),
        ]

    def __str__(self):
        return self.asset_name


class AssignmentHistory(models.Model):
    class Action(models.TextChoices):
        ASSIGNED = 'assigned', 'Assigned'
        RETURNED = 'returned', 'Returned'
        REASSIGNED = 'reassigned', 'Reassigned'
        RECOVERY_PENDING = 'recovery_pending', 'Recovery pending'
        MISSING_REPORTED = 'missing_reported', 'Missing reported'
        INSPECTION_RELEASED = 'inspection_released', 'Inspection released'

    class Source(models.TextChoices):
        LEGACY = 'legacy', 'Legacy record'
        STAFF = 'staff', 'Staff action'
        SCHEDULED = 'scheduled', 'Scheduled process'

    class ReceiptCondition(models.TextChoices):
        USABLE = 'usable', 'Usable'
        DAMAGED = 'damaged', 'Damaged'

    asset = models.ForeignKey(Asset, on_delete=models.PROTECT, related_name='assignment_history')
    employee = models.ForeignKey(Employee, on_delete=models.PROTECT, related_name='assignment_history', null=True, blank=True)
    action = models.CharField(max_length=24, choices=Action.choices)
    occurred_at = models.DateTimeField(null=True, blank=True, default=timezone.now)
    observed_at = models.DateTimeField(null=True, blank=True)
    receipt_condition = models.CharField(max_length=8, choices=ReceiptCondition.choices, blank=True)
    note = models.TextField(blank=True)
    source = models.CharField(max_length=12, choices=Source.choices, default=Source.LEGACY)
    case = models.ForeignKey('AssetExceptionCase', on_delete=models.PROTECT, null=True, blank=True,
                             related_name='events')
    actor = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, blank=True,
                              on_delete=models.SET_NULL, related_name='asset_assignment_actions')

    class Meta:
        ordering = ['-occurred_at', '-pk']

    def __str__(self):
        return f'{self.asset} {self.get_action_display()} {self.employee or ""}'


class AssetExceptionCase(models.Model):
    class Kind(models.TextChoices):
        RECOVERY = 'recovery', 'Recovery pending'
        MISSING = 'missing', 'Reported missing'
        INSPECTION = 'inspection', 'Inspection hold'

    asset = models.ForeignKey(Asset, on_delete=models.PROTECT, related_name='exception_cases')
    kind = models.CharField(max_length=12, choices=Kind.choices)
    reason = models.TextField()
    opened_at = models.DateTimeField(default=timezone.now)
    observed_at = models.DateTimeField(null=True, blank=True)
    opened_by = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, blank=True,
                                  on_delete=models.SET_NULL, related_name='opened_asset_cases')
    source = models.CharField(max_length=12, choices=AssignmentHistory.Source.choices)
    resolved_at = models.DateTimeField(null=True, blank=True)
    resolved_by = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, blank=True,
                                    on_delete=models.SET_NULL, related_name='resolved_asset_cases')
    resolution_note = models.TextField(blank=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(fields=['asset'], condition=models.Q(resolved_at__isnull=True),
                                    name='one_open_exception_case_per_asset'),
            models.CheckConstraint(
                condition=(models.Q(resolved_at__isnull=True, resolution_note='')
                           | (models.Q(resolved_at__isnull=False) & ~models.Q(resolution_note=''))),
                name='asset_case_resolution_note_required',
            ),
        ]
