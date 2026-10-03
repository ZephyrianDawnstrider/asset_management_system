import csv
from io import StringIO
from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.core.exceptions import ValidationError
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
        response = self.client.get(reverse('employee_overview'))
        self.assertEqual(response.status_code, 302)
        self.assertIn('/accounts/login/', response['Location'])

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
        self.assertEqual(response.status_code, 302)
        self.first.refresh_from_db()
        self.assertFalse(self.first.is_active)
        self.assertEqual(self.first.name, 'Ari Updated')
