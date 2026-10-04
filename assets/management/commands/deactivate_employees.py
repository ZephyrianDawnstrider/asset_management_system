from django.core.management.base import BaseCommand
from django.utils import timezone
from assets.models import Employee
from assets.services import deactivate_employee

class Command(BaseCommand):
    help = 'Deactivates employees after their final active day while preserving unresolved asset custody.'

    def handle(self, *args, **options):
        today = timezone.now().date()
        employees_to_deactivate = Employee.objects.filter(is_active=True, exit_date__lt=today)

        for employee in employees_to_deactivate:
            deactivate_employee(employee.pk, exit_date=employee.exit_date)

            self.stdout.write(self.style.SUCCESS(f'Deactivated employee {employee.name} ({employee.employee_id}); unresolved assets remain linked for review.'))

        self.stdout.write(self.style.SUCCESS('Finished deactivating employees.'))
