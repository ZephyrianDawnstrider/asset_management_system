from django.core.management.base import BaseCommand
from django.utils import timezone
from assets.models import Employee, Asset

class Command(BaseCommand):
    help = 'Deactivates employees and unassigns their assets if their exit date has passed.'

    def handle(self, *args, **options):
        today = timezone.now().date()
        employees_to_deactivate = Employee.objects.filter(is_active=True, exit_date__lt=today)

        for employee in employees_to_deactivate:
            employee.is_active = False
            employee.save()

            Asset.objects.filter(assigned_to=employee).update(assigned_to=None)

            self.stdout.write(self.style.SUCCESS(f'Successfully deactivated employee {employee.name} ({employee.employee_id}) and unassigned their assets.'))

        self.stdout.write(self.style.SUCCESS('Finished deactivating employees.'))
