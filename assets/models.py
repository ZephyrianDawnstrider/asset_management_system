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
    asset_type = models.ForeignKey(AssetType, on_delete=models.CASCADE)
    unique_identifier = models.CharField(max_length=255, unique=True)
    asset_name = models.CharField(max_length=255)
    assigned_to = models.ForeignKey(Employee, on_delete=models.SET_NULL, null=True, blank=True)
    details = models.TextField(blank=True)
    is_active = models.BooleanField(default=True)

    class Meta:
        unique_together = ('asset_type', 'unique_identifier')

    def __str__(self):
        return self.asset_name


class AssignmentHistory(models.Model):
    class Action(models.TextChoices):
        ASSIGNED = 'assigned', 'Assigned'
        RETURNED = 'returned', 'Returned'
        REASSIGNED = 'reassigned', 'Reassigned'

    asset = models.ForeignKey(Asset, on_delete=models.PROTECT, related_name='assignment_history')
    employee = models.ForeignKey(Employee, on_delete=models.PROTECT, related_name='assignment_history')
    action = models.CharField(max_length=16, choices=Action.choices)
    occurred_at = models.DateTimeField(null=True, blank=True, default=timezone.now)
    actor = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, blank=True,
                              on_delete=models.SET_NULL, related_name='asset_assignment_actions')

    class Meta:
        ordering = ['-occurred_at', '-pk']

    def __str__(self):
        return f'{self.asset} {self.get_action_display()} {self.employee}'
