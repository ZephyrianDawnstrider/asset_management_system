import csv
from datetime import datetime, timezone as dt_timezone
from io import StringIO
from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.core.exceptions import ValidationError
from django.core.management import call_command
from django.db.models.deletion import ProtectedError
from django.test import TestCase, Client
from django.urls import reverse

from .models import Asset, AssetType, AssignmentHistory, Employee
from .forms import AssetAssignmentForm
from .services import change_asset_assignment, deactivate_employee


class AssetWorkflowTests(TestCase):
    def setUp(self):
        User = get_user_model()
        self.staff = User.objects.create_user(username='operator', password='test-pass-123', is_staff=True)
        self.nonstaff = User.objects.create_user(username='member', password='test-pass-123')
        self.superuser = User.objects.create_superuser(username='root', password='test-pass-123', email='root@example.test')
        self.first = Employee.objects.create(employee_id='EMP-01', name='Ari Example', department='Ops', designation='Lead', start_date='2026-01-01')
        self.second = Employee.objects.create(employee_id='EMP-02', name='Sam Example', department='Ops', designation='Analyst', start_date='2026-01-02')
        self.kind = AssetType.objects.create(name='Laptop', identification_type_label='Serial', object_description='Portable computer')
        self.asset = Asset.objects.create(asset_type=self.kind, unique_identifier='SERIAL-001', asset_name='Work laptop')

    def test_staff_can_assign_return_and_reassign_with_history(self):
        self.client.force_login(self.staff)
        assign = reverse('assign_asset_to_employee')
        response = self.client.post(assign, {'employee_id': self.first.employee_id, 'asset_id': self.asset.pk})
        self.assertEqual(response.status_code, 200)
        self.assertTrue(response.json()['success'])
        self.asset.refresh_from_db()
        self.assertEqual(self.asset.assigned_to, self.first)

        response = self.client.post(reverse('unassign_asset', args=[self.asset.pk]),
                                    {'expected_employee_id': self.first.pk})
        self.assertEqual(response.status_code, 200)
        self.asset.refresh_from_db()
        self.assertIsNone(self.asset.assigned_to)

        response = self.client.post(assign, {'employee_id': self.second.employee_id, 'asset_id': self.asset.pk})
        self.assertEqual(response.status_code, 200)
        self.assertEqual(list(self.asset.assignment_history.order_by('pk').values_list('action', 'employee__employee_id')),
                         [('assigned', self.first.employee_id), ('returned', self.first.employee_id), ('assigned', self.second.employee_id)])
        self.assertTrue(all(entry.actor == self.staff for entry in self.asset.assignment_history.all()))

    def test_return_rejects_stale_employee_id(self):
        self.asset.assigned_to = self.second
        self.asset.save(update_fields=['assigned_to'])
        self.client.force_login(self.staff)
        response = self.client.post(reverse('unassign_asset', args=[self.asset.pk]),
                                    {'expected_employee_id': self.first.pk})
        self.assertEqual(response.status_code, 409)
        self.asset.refresh_from_db()
        self.assertEqual(self.asset.assigned_to, self.second)
        self.assertFalse(AssignmentHistory.objects.exists())

    def test_inactive_entities_cannot_be_assigned(self):
        self.client.force_login(self.staff)
        self.second.is_active = False
        self.second.save(update_fields=['is_active'])
        response = self.client.post(reverse('assign_asset_to_employee'),
                                    {'employee_id': self.second.employee_id, 'asset_id': self.asset.pk})
        self.assertEqual(response.status_code, 404)
        self.kind.is_active = False
        self.kind.save(update_fields=['is_active'])
        response = self.client.get(reverse('unassigned_assets_api', args=[self.kind.pk]))
        self.assertEqual(response.status_code, 404)
        self.assertFalse(AssignmentHistory.objects.exists())

    def test_authenticated_nonstaff_cannot_read_or_mutate_operations(self):
        self.client.force_login(self.nonstaff)
        urls = [
            reverse('employee_overview'), reverse('employee_overview_csv'),
            reverse('employee_list'), reverse('asset_list'), reverse('asset_assign'),
            reverse('employee_detail', args=[self.first.employee_id]),
            reverse('unassigned_assets_api', args=[self.kind.pk]),
        ]
        for url in urls:
            with self.subTest(url=url):
                self.assertEqual(self.client.get(url).status_code, 403)
        response = self.client.post(reverse('assign_asset_to_employee'),
                                    {'employee_id': self.first.employee_id, 'asset_id': self.asset.pk})
        self.assertEqual(response.status_code, 403)
        self.asset.refresh_from_db()
        self.assertIsNone(self.asset.assigned_to)
        self.assertFalse(AssignmentHistory.objects.exists())

    def test_anonymous_is_redirected_to_login(self):
        with self.assertNumQueries(0):
            landing = self.client.get(reverse('home'))
        self.assertEqual(landing.status_code, 200)
        self.assertContains(landing, 'One asset. A complete custody decision.')
        self.assertContains(landing, 'SIMULATION ONLY · SYNTHETIC DATA')
        self.assertContains(landing, 'assets/js/public-demo.js')
        self.assertNotContains(landing, self.first.name)
        self.assertNotContains(landing, self.asset.unique_identifier)
        response = self.client.get(reverse('employee_overview'))
        self.assertEqual(response.status_code, 302)
        self.assertIn('/accounts/login/', response['Location'])
        history_response = self.client.get(reverse('asset_history', args=[self.asset.pk]))
        self.assertEqual(history_response.status_code, 302)
        self.assertIn('/accounts/login/', history_response['Location'])

    def test_overview_rows_and_csv_escape_formula_cells(self):
        self.first.name = '=2+3'
        self.first.save(update_fields=['name'])
        self.client.force_login(self.staff)
        response = self.client.get(reverse('employee_overview'))
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.context['employee_rows'][0]['employee'], self.first)
        response = self.client.get(reverse('employee_overview_csv'))
        self.assertEqual(response.status_code, 200)
        rows = list(csv.reader(StringIO(response.content.decode('utf-8'))))
        self.assertEqual(rows[1][1], "'=2+3")
        self.assertEqual(rows[1][7], 'No active assets')

    def test_operations_overview_is_staff_only_and_links_to_real_history(self):
        self.client.force_login(self.staff)
        change_asset_assignment(self.asset.pk, self.first, self.staff, expected_employee_id=None)
        change_asset_assignment(self.asset.pk, None, self.staff, expected_employee_id=self.first.pk)
        AssignmentHistory.objects.create(asset=self.asset, employee=self.first, action='assigned', occurred_at=None)
        response = self.client.get(reverse('employee_overview'))
        self.assertEqual(response.status_code, 200)
        self.assertEqual([asset.pk for asset in response.context['available_assets']], [self.asset.pk])
        self.assertEqual([event.action for event in response.context['recent_custody']], ['returned', 'assigned', 'assigned'])
        self.assertIsNone(response.context['recent_custody'][-1].occurred_at)
        self.assertContains(response, reverse('asset_history', args=[self.asset.pk]))
        self.client.force_login(self.nonstaff)
        self.assertEqual(self.client.get(reverse('employee_overview')).status_code, 403)

    def test_asset_register_csv_uses_filters_all_pages_and_escapes_formulas(self):
        second = Asset.objects.create(asset_type=self.kind, unique_identifier='+2+3', asset_name='=Injected',
                                      details='\t@formula')
        for n in range(21):
            Asset.objects.create(asset_type=self.kind, unique_identifier=f'EXTRA-{n:02}', asset_name='Other')
        self.client.force_login(self.staff)
        response = self.client.get(reverse('asset_register_csv'), {'q': 'Injected', 'status': 'available', 'page': '2'})
        self.assertEqual(response.status_code, 200)
        rows = list(csv.reader(StringIO(response.content.decode('utf-8'))))
        self.assertEqual(len(rows), 2)
        self.assertEqual(rows[1][:4], ["'=Injected", 'Laptop', "'+2+3", "'\t@formula"])
        filtered = self.client.get(reverse('asset_register_csv'), {'asset_type': self.kind.pk, 'status': 'available'})
        self.assertEqual(len(list(csv.reader(StringIO(filtered.content.decode('utf-8'))))), 24)
        second.is_active = False
        second.save(update_fields=['is_active'])
        self.assertEqual(len(list(csv.reader(StringIO(self.client.get(reverse('asset_register_csv'),
            {'q': 'Injected'}).content.decode('utf-8'))))), 1)
        self.client.force_login(self.nonstaff)
        self.assertEqual(self.client.get(reverse('asset_register_csv')).status_code, 403)
        self.client.logout()
        self.assertEqual(self.client.get(reverse('asset_register_csv')).status_code, 302)

    def test_employee_and_asset_creation_and_global_serial_uniqueness(self):
        second_type = AssetType.objects.create(name='Phone', identification_type_label='IMEI', object_description='Phone')
        duplicate = AssetAssignmentForm(data={
            'asset_type': second_type.pk, 'asset_name': 'Other device',
            'unique_identifier': self.asset.unique_identifier, 'details': '',
        })
        self.assertFalse(duplicate.is_valid())
        self.assertIn('unique_identifier', duplicate.errors)

        self.client.force_login(self.staff)
        response = self.client.post(reverse('employee_create'), {
            'employee_id': 'EMP-NEW', 'name': 'Taylor New', 'department': 'Operations',
            'designation': 'Coordinator', 'start_date': '2026-03-01',
        })
        self.assertEqual(response.status_code, 302)
        self.assertTrue(Employee.objects.filter(employee_id='EMP-NEW').exists())
        response = self.client.post(reverse('asset_assign'), {
            'asset_type': self.kind.pk, 'asset_name': 'New laptop',
            'unique_identifier': 'SERIAL-NEW', 'details': 'Synthetic test item',
        })
        self.assertEqual(response.status_code, 302)
        self.assertTrue(Asset.objects.filter(unique_identifier='SERIAL-NEW', assigned_to__isnull=True).exists())

    def test_history_prevents_hard_delete_of_employee_and_asset(self):
        self.client.force_login(self.staff)
        self.client.post(reverse('assign_asset_to_employee'),
                         {'employee_id': self.first.employee_id, 'asset_id': self.asset.pk})
        self.client.post(reverse('employee_delete', args=[self.first.employee_id]))
        self.first.refresh_from_db()
        self.assertFalse(self.first.is_active)
        self.assertTrue(AssignmentHistory.objects.filter(employee=self.first).exists())
        with self.assertRaises(ProtectedError):
            self.first.delete()
        with self.assertRaises(ProtectedError):
            self.asset.delete()

    def test_csrf_is_required_for_assignment(self):
        csrf_client = Client(enforce_csrf_checks=True)
        csrf_client.force_login(self.staff)
        response = csrf_client.post(reverse('assign_asset_to_employee'),
                                    {'employee_id': self.first.employee_id, 'asset_id': self.asset.pk})
        self.assertEqual(response.status_code, 403)

    def test_stale_expected_owner_cannot_reassign_or_write_history(self):
        self.asset.assigned_to = self.first
        self.asset.save(update_fields=['assigned_to'])
        with self.assertRaises(ValidationError):
            change_asset_assignment(self.asset.pk, self.second, self.staff, expected_employee_id=None)
        self.asset.refresh_from_db()
        self.assertEqual(self.asset.assigned_to, self.first)
        self.assertFalse(AssignmentHistory.objects.exists())

    def test_superuser_admin_is_read_only_for_inventory(self):
        self.client.force_login(self.superuser)
        response = self.client.get(f'/admin/assets/asset/{self.asset.pk}/change/')
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'assigned_to')
        response = self.client.post(f'/admin/assets/asset/{self.asset.pk}/change/',
                                    {'asset_name': 'Changed', 'unique_identifier': 'SERIAL-001'})
        self.assertEqual(response.status_code, 403)
        self.asset.refresh_from_db()
        self.assertEqual(self.asset.asset_name, 'Work laptop')
        self.assertEqual(self.client.get('/admin/auth/user/').status_code, 200)
        self.assertEqual(self.client.post(f'/admin/auth/user/{self.staff.pk}/delete/').status_code, 403)

    def test_employee_offboarding_rolls_back_every_return_on_failure(self):
        other = Asset.objects.create(asset_type=self.kind, unique_identifier='SERIAL-002', asset_name='Second laptop', assigned_to=self.first)
        self.asset.assigned_to = self.first
        self.asset.save(update_fields=['assigned_to'])
        from . import services
        original = services.change_asset_assignment
        calls = 0

        def fail_on_second(*args, **kwargs):
            nonlocal calls
            calls += 1
            if calls == 2:
                raise ValidationError('simulated second transition failure')
            return original(*args, **kwargs)

        with patch('assets.services.change_asset_assignment', side_effect=fail_on_second):
            with self.assertRaises(ValidationError):
                deactivate_employee(self.first.pk, self.staff)
        self.first.refresh_from_db()
        self.asset.refresh_from_db()
        other.refresh_from_db()
        self.assertTrue(self.first.is_active)
        self.assertEqual(self.asset.assigned_to, self.first)
        self.assertEqual(other.assigned_to, self.first)
        self.assertFalse(AssignmentHistory.objects.exists())

    def test_employee_edit_does_not_revive_concurrently_deactivated_record(self):
        self.client.force_login(self.staff)
        self.first.is_active = False
        self.first.save(update_fields=['is_active'])
        response = self.client.post(reverse('employee_update', args=[self.first.pk]), {
            'employee_id': self.first.employee_id, 'name': 'Ari Updated', 'department': 'Ops',
            'designation': 'Lead', 'start_date': '2026-01-01', 'exit_date': '',
        })
        self.assertEqual(response.status_code, 404)
        self.first.refresh_from_db()
        self.assertFalse(self.first.is_active)
        self.assertEqual(self.first.name, 'Ari Example')

    def test_employee_list_filters_paginates_and_preserves_encoded_query(self):
        for n in range(25):
            Employee.objects.create(employee_id=f'EMP-X{n:02}', name=f'Person {n:02}',
                                    department='Research & Development', designation='Engineer', start_date='2026-02-01')
        self.client.force_login(self.staff)
        url = reverse('employee_list')
        response = self.client.get(url, {'q': 'Research & Development', 'department': 'Research & Development', 'page': '2'})
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.context['employees'].paginator.count, 25)
        self.assertEqual(len(response.context['employees']), 5)
        self.assertEqual(response.context['result_count'], 25)
        self.assertEqual(response.context['filter_q'], 'Research & Development')
        self.assertEqual(response.context['filter_department'], 'Research & Development')
        self.assertIn('q=Research+%26+Development', response.context['page_query'])
        self.assertIn('department=Research+%26+Development', response.context['page_query'])
        malformed = self.client.get(url, {'page': 'invalid'})
        self.assertEqual(malformed.status_code, 200)
        self.assertEqual(malformed.context['employees'].number, 1)
        out_of_range = self.client.get(url, {'page': '999'})
        self.assertEqual(out_of_range.context['employees'].number, 2)
        no_results = self.client.get(url, {'q': '<no such employee & item>'})
        self.assertEqual(no_results.status_code, 200)
        self.assertEqual(no_results.context['result_count'], 0)

    def test_asset_list_filters_type_status_holder_and_pagination(self):
        phone_type = AssetType.objects.create(name='Phone', identification_type_label='IMEI', object_description='Mobile')
        for n in range(23):
            Asset.objects.create(asset_type=phone_type, unique_identifier=f'PHONE-{n:02}', asset_name=f'Phone {n:02}',
                                 assigned_to=self.second if n == 0 else None)
        self.client.force_login(self.staff)
        response = self.client.get(reverse('asset_list'), {'q': 'Sam Example', 'asset_type': phone_type.pk,
                                                            'status': 'assigned', 'page': '1'})
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.context['result_count'], 1)
        self.assertEqual(response.context['assets'][0].assigned_to, self.second)
        self.assertEqual(response.context['filter_asset_type'], str(phone_type.pk))
        self.assertEqual(response.context['filter_status'], 'assigned')
        self.assertIn('q=Sam+Example', response.context['page_query'])
        self.assertIn('asset_type=', response.context['page_query'])
        self.assertIn('status=assigned', response.context['page_query'])
        malformed = self.client.get(reverse('asset_list'), {'asset_type': 'nonsense', 'status': 'other', 'page': 'oops'})
        self.assertEqual(malformed.status_code, 200)
        self.assertEqual(malformed.context['filter_asset_type'], '')
        self.assertEqual(malformed.context['filter_status'], '')
        huge_id = self.client.get(reverse('asset_list'), {'asset_type': '9' * 200})
        self.assertEqual(huge_id.status_code, 200)
        page_two = self.client.get(reverse('asset_list'), {'asset_type': phone_type.pk, 'page': '2'})
        self.assertEqual(page_two.context['assets'].number, 2)
        self.assertEqual(len(page_two.context['assets']), 3)

    def test_overview_totals_stay_global_while_employee_results_are_filtered(self):
        for n in range(22):
            Employee.objects.create(employee_id=f'EMP-P{n:02}', name=f'Page Person {n:02}',
                                    department='Support', designation='Agent', start_date='2026-02-01')
        self.asset.assigned_to = self.first
        self.asset.save(update_fields=['assigned_to'])
        self.client.force_login(self.staff)
        response = self.client.get(reverse('employee_overview'), {'department': 'Support', 'page': '2'})
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.context['total_employees'], 24)
        self.assertEqual(response.context['total_assets'], 1)
        self.assertEqual(response.context['assigned_assets'], 1)
        self.assertEqual(response.context['unassigned_assets_count'], 0)
        self.assertEqual(response.context['result_count'], 22)
        self.assertEqual(response.context['employees'].number, 2)
        self.assertEqual(len(response.context['employee_rows']), 2)
        self.assertIn('department=Support', response.context['page_query'])

    def test_offboarding_queue_uses_final_day_window_and_active_custody(self):
        self.first.exit_date = '2026-10-03'
        self.first.save(update_fields=['exit_date'])
        self.second.exit_date = '2026-10-18'
        self.second.save(update_fields=['exit_date'])
        self.asset.assigned_to = self.first
        self.asset.save(update_fields=['assigned_to'])
        for suffix, exit_date, active_employee, active_asset in (
            ('FUTURE', '2026-10-19', True, True),
            ('NONE', None, True, True),
            ('RETIRED', '2026-10-04', True, False),
            ('INACTIVE', '2026-10-02', False, True),
        ):
            employee = Employee.objects.create(employee_id=f'EMP-{suffix}', name=suffix, department='Ops',
                                               designation='Analyst', start_date='2026-01-01',
                                               exit_date=exit_date, is_active=active_employee)
            Asset.objects.create(asset_type=self.kind, unique_identifier=f'SERIAL-{suffix}', asset_name=suffix,
                                 assigned_to=employee, is_active=active_asset)
        Asset.objects.create(asset_type=self.kind, unique_identifier='SERIAL-BOUNDARY', asset_name='Boundary asset',
                             assigned_to=self.second)
        self.client.force_login(self.staff)
        with patch('assets.views.timezone.now', return_value=datetime(2026, 10, 4, 12, tzinfo=dt_timezone.utc)):
            response = self.client.get(reverse('employee_overview'))
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.context['offboarding_total'], 2)
        self.assertEqual([(person.employee_id, person.held_asset_count) for person in response.context['offboarding_queue']],
                         [('EMP-01', 1), ('EMP-02', 1)])
        self.assertContains(response, 'Final day passed')
        self.assertContains(response, 'Upcoming final day')
        self.assertContains(response, 'A final active day is not a return due date.')
        self.client.force_login(self.nonstaff)
        self.assertEqual(self.client.get(reverse('employee_overview')).status_code, 403)
        self.client.logout()
        self.assertEqual(self.client.get(reverse('employee_overview')).status_code, 302)

    def test_offboarding_detail_deactivation_preserves_history_and_becomes_read_only(self):
        self.first.exit_date = '2026-10-04'
        self.first.save(update_fields=['exit_date'])
        self.asset.assigned_to = self.first
        self.asset.save(update_fields=['assigned_to'])
        self.client.force_login(self.staff)
        detail_url = reverse('employee_detail', args=[self.first.employee_id])
        active = self.client.get(detail_url)
        self.assertContains(active, 'Offboarding checklist')
        self.assertContains(active, 'Deactivate now and return held assets')
        self.assertContains(active, 'Return asset')
        response = self.client.post(reverse('employee_soft_delete', args=[self.first.employee_id]))
        self.assertEqual(response.status_code, 302)
        self.first.refresh_from_db()
        self.asset.refresh_from_db()
        self.assertFalse(self.first.is_active)
        self.assertIsNone(self.asset.assigned_to_id)
        self.assertTrue(AssignmentHistory.objects.filter(asset=self.asset, employee=self.first, action='returned').exists())
        inactive = self.client.get(detail_url)
        self.assertContains(inactive, 'Inactive record · read-only')
        self.assertContains(inactive, 'Returned')
        self.assertNotContains(inactive, 'Edit employee')
        self.assertNotContains(inactive, 'Return asset')
        self.assertNotContains(inactive, 'Assign available equipment')
        self.assertNotContains(inactive, 'Deactivate now and return held assets')
        self.assertEqual(self.client.get(reverse('employee_update', args=[self.first.pk])).status_code, 404)
        self.assertEqual(self.client.get(reverse('employee_delete', args=[self.first.employee_id])).status_code, 404)

    def test_employee_and_retired_asset_history_are_fully_paginated(self):
        for n in range(21):
            AssignmentHistory.objects.create(asset=self.asset, employee=self.first, action='returned', actor=self.staff)
        # Current employee history has more than one page and keeps page selection stable.
        self.client.force_login(self.staff)
        employee_response = self.client.get(reverse('employee_detail', args=[self.first.employee_id]), {'history_page': '2'})
        self.assertEqual(employee_response.status_code, 200)
        self.assertEqual(employee_response.context['history_page'].paginator.count, 21)
        self.assertEqual(employee_response.context['history_page'].number, 2)
        self.assertEqual(len(employee_response.context['assignment_history']), 1)
        employee_first_page = self.client.get(reverse('employee_detail', args=[self.first.employee_id]), {'history_page': '1'})
        self.assertContains(employee_first_page, 'history_page=2')

        self.asset.is_active = False
        self.asset.save(update_fields=['is_active'])
        asset_response = self.client.get(reverse('asset_history', args=[self.asset.pk]), {'history_page': '2'})
        self.assertEqual(asset_response.status_code, 200)
        self.assertFalse(asset_response.context['asset'].is_active)
        self.assertEqual(asset_response.context['history_page'].paginator.count, 21)
        self.assertEqual(asset_response.context['history_page'].number, 2)
        asset_first_page = self.client.get(reverse('asset_history', args=[self.asset.pk]), {'history_page': '1'})
        self.assertContains(asset_first_page, 'history_page=2')

    def test_both_expired_employee_commands_deactivate_after_final_active_day(self):
        base_date = datetime(2026, 6, 15, 12, 0, tzinfo=dt_timezone.utc)
        for command_name in ('deactivate_employees', 'soft_delete_expired_employees'):
            with self.subTest(command=command_name):
                employees = []
                for suffix, exit_date in (('Y', '2026-06-14'), ('T', '2026-06-15'), ('F', '2026-06-16')):
                    employee = Employee.objects.create(employee_id=f'CMD-{command_name}-{suffix}', name=f'{suffix} Employee',
                                                       department='Ops', designation='Staff', start_date='2026-01-01',
                                                       exit_date=exit_date)
                    employees.append(employee)
                    Asset.objects.create(asset_type=self.kind,
                                         unique_identifier=f'{command_name}-{suffix}', asset_name=f'{suffix} asset',
                                         assigned_to=employee)
                command_module = __import__(f'assets.management.commands.{command_name}', fromlist=['timezone'])
                with patch.object(command_module.timezone, 'now', return_value=base_date):
                    call_command(command_name, verbosity=0)
                for employee, expected_active in zip(employees, (False, True, True)):
                    employee.refresh_from_db()
                    self.assertEqual(employee.is_active, expected_active)
                    asset = Asset.objects.get(unique_identifier=f'{command_name}-{employee.employee_id[-1]}')
                    if expected_active:
                        self.assertEqual(asset.assigned_to_id, employee.pk)
                        self.assertFalse(AssignmentHistory.objects.filter(asset=asset).exists())
                    else:
                        self.assertIsNone(asset.assigned_to_id)
                        self.assertEqual(AssignmentHistory.objects.filter(asset=asset, action='returned').count(), 1)

    def test_employee_edit_uses_exit_date_as_final_active_day(self):
        self.client.force_login(self.staff)
        url = reverse('employee_update', args=[self.first.pk])
        data = {'employee_id': self.first.employee_id, 'name': self.first.name, 'department': self.first.department,
                'designation': self.first.designation, 'start_date': '2026-01-01', 'exit_date': '2026-10-03'}
        with patch('assets.views.timezone.now', return_value=datetime(2026, 10, 3, 12, 0, tzinfo=dt_timezone.utc)):
            response = self.client.post(url, data)
        self.assertEqual(response.status_code, 302)
        self.first.refresh_from_db()
        self.assertTrue(self.first.is_active)
        yesterday = dict(data, exit_date='2026-10-02')
        self.asset.assigned_to = self.first
        self.asset.save(update_fields=['assigned_to'])
        with patch('assets.views.timezone.now', return_value=datetime(2026, 10, 3, 12, 0, tzinfo=dt_timezone.utc)):
            response = self.client.post(url, yesterday)
        self.assertEqual(response.status_code, 302)
        self.first.refresh_from_db()
        self.asset.refresh_from_db()
        self.assertFalse(self.first.is_active)
        self.assertIsNone(self.asset.assigned_to_id)
        self.assertTrue(AssignmentHistory.objects.filter(asset=self.asset, employee=self.first, action='returned').exists())
