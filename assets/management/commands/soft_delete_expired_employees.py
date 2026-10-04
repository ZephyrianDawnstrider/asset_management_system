from django.core.management.base import BaseCommand
from django.utils import timezone
from assets.models import Employee
from assets.services import deactivate_employee
from asset_management.write_fence import require_writes_unpaused

class Command(BaseCommand):
    help = 'Deactivate employees whose final active day has passed without claiming asset receipt'

    def handle(self, *args, **options):
        require_writes_unpaused()
        today = timezone.now().date()
        expired_employees = Employee.objects.filter(exit_date__lt=today, is_active=True)
        count = 0
        for employee in expired_employees:
            deactivate_employee(employee.pk, exit_date=employee.exit_date)
            self.stdout.write(self.style.SUCCESS(f'Soft deleted employee {employee.employee_id}'))
            count += 1
        self.stdout.write(self.style.SUCCESS(f'Processed {count} employees'))
