from django.core.management.base import BaseCommand
from assets.models import Employee

class Command(BaseCommand):
    help = 'Populate initial employee data'

    def handle(self, *args, **options):
        employees_data = [
            {'employee_id': '1', 'department': 'account', 'name': 'Aditiya', 'designation': 'Accountant', 'start_date': '2023-01-01'},
            {'employee_id': '2', 'department': 'head', 'name': 'Benny', 'designation': 'Head', 'start_date': '2023-01-01'},
            {'employee_id': '3', 'department': 'Backend dev', 'name': 'Krishnan', 'designation': 'Backend Developer', 'start_date': '2023-01-01'},
        ]

        for emp_data in employees_data:
            Employee.objects.get_or_create(
                employee_id=emp_data['employee_id'],
                defaults=emp_data
            )
            self.stdout.write(self.style.SUCCESS(f'Created employee {emp_data["name"]}'))

        self.stdout.write(self.style.SUCCESS('Successfully populated employees'))
