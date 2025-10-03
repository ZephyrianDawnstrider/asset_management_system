from django.db import models

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

    def __str__(self):
        return self.name

class Asset(models.Model):
    asset_type = models.ForeignKey(AssetType, on_delete=models.CASCADE)
    unique_identifier = models.CharField(max_length=255)
    asset_name = models.CharField(max_length=255)
    assigned_to = models.ForeignKey(Employee, on_delete=models.SET_NULL, null=True, blank=True)
    details = models.TextField(blank=True)

    class Meta:
        unique_together = ('asset_type', 'unique_identifier')

    def __str__(self):
        return self.asset_name
