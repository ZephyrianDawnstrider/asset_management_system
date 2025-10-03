from django.core.management.base import BaseCommand
from assets.models import Employee
from datetime import date

class Command(BaseCommand):
    help = 'Populate initial employee data for testing'

    def handle(self, *args, **options):
        employees_data = [
            {
                'employee_id': 'EMP001',
                'name': 'John Doe',
                'department': 'IT',
                'designation': 'Software Engineer',
                'start_date': date(2023, 1, 15)
            },
            {
                'employee_id': 'EMP002',
                'name': 'Jane Smith',
                'department': 'HR',
                'designation': 'HR Manager',
                'start_date': date(2022, 6, 1)
            },
            {
                'employee_id': 'EMP003',
                'name': 'Bob Johnson',
                'department': 'Finance',
                'designation': 'Accountant',
                'start_date': date(2021, 3, 10)
            },
            {
                'employee_id': 'EMP004',
                'name': 'Alice Brown',
                'department': 'IT',
                'designation': 'DevOps Engineer',
                'start_date': date(2023, 8, 20)
            },
            {
                'employee_id': 'EMP005',
                'name': 'Charlie Wilson',
                'department': 'Marketing',
                'designation': 'Marketing Specialist',
                'start_date': date(2022, 11, 5)
            },
        ]

        created = 0
        for data in employees_data:
            employee, created_new = Employee.objects.get_or_create(
                employee_id=data['employee_id'],
                defaults=data
            )
            if created_new:
                created += 1

        self.stdout.write(
            self.style.SUCCESS(f'Successfully created {created} new employees')
        )
