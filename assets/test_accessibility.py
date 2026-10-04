"""Focused staff navigation and server-rendered form error contracts."""

from django import forms
from django.contrib.auth import get_user_model
from django.template.loader import render_to_string
from django.test import RequestFactory, TestCase
from django.urls import resolve, reverse

from .models import Asset, AssetType, Employee


class StaffAccessibilityTests(TestCase):
    def setUp(self):
        self.staff = get_user_model().objects.create_user(
            username='a11y-operator', password='local-test-only', is_staff=True,
        )
        self.employee = Employee.objects.create(
            employee_id='A11Y-01', name='Accessible Example', department='Ops',
            designation='Operator', start_date='2026-01-01',
        )
        self.kind = AssetType.objects.create(
            name='Accessibility laptop', identification_type_label='Serial',
            object_description='Test fixture',
        )
        self.asset = Asset.objects.create(
            asset_type=self.kind, unique_identifier='A11Y-ASSET', asset_name='Test asset',
        )
        self.client.force_login(self.staff)

    def test_each_staff_destination_has_one_current_page_link(self):
        destinations = (
            (reverse('employee_overview'), reverse('employee_overview'), 'page'),
            (reverse('employee_list'), reverse('employee_list'), 'page'),
            (reverse('employee_detail', args=[self.employee.employee_id]), reverse('employee_list'), 'true'),
            (reverse('asset_list'), reverse('asset_list'), 'page'),
            (reverse('asset_history', args=[self.asset.pk]), reverse('asset_list'), 'true'),
            (reverse('asset_assign'), reverse('asset_assign'), 'page'),
            (reverse('assettype_list'), reverse('assettype_list'), 'page'),
        )
        for page, active_link, current in destinations:
            with self.subTest(page=page):
                response = self.client.get(page)
                self.assertEqual(response.status_code, 200)
                html = response.content.decode()
                self.assertEqual(html.count('aria-current='), 1)
                self.assertIn(f'href="{active_link}" class="nav-link is-current" aria-current="{current}"', html)
                self.assertIn('a11y-operator', html)
                for label in ('Overview', 'Employees', 'Asset register', 'Add an asset', 'Asset types', 'Sign out'):
                    self.assertIn(label, html)

    def test_invalid_forms_render_addressable_errors_and_focus_script(self):
        forms_to_check = (
            (reverse('employee_create'), 'id_employee_id-error'),
            (reverse('asset_update', args=[self.asset.pk]), 'id_asset_type-error'),
            (reverse('assettype_create'), 'id_name-error'),
            (reverse('asset_assign'), 'id_asset_type-error'),
        )
        for url, error_id in forms_to_check:
            with self.subTest(url=url):
                response = self.client.post(url, {})
                self.assertEqual(response.status_code, 200)
                self.assertContains(response, 'js-server-error-form')
                self.assertContains(response, f'id="{error_id}"')
                self.assertContains(response, 'assets/js/form-errors.js')
                self.assertNotContains(self.client.get(url), 'assets/js/form-errors.js')

    def test_non_field_error_has_focusable_fallback(self):
        request = RequestFactory().get(reverse('employee_create'))
        request.user = self.staff
        request.resolver_match = resolve(request.path)
        form = forms.Form(data={})
        form.is_valid()
        form.add_error(None, 'Review the combined details.')
        html = render_to_string('assets/employee_form.html', {'form': form}, request=request)
        self.assertIn('id="form-non-field-errors"', html)
        self.assertIn('role="alert" tabindex="-1"', html)
        self.assertIn('Review the combined details.', html)

    def test_public_demo_keeps_its_own_navigation(self):
        self.client.logout()
        response = self.client.get(reverse('home'))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'class="nav-list public-nav"')
        self.assertNotContains(response, 'staff-nav')
