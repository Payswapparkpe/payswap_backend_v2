"""
Tests for Super Admin URL redirects (Super Admin UI removed; URLs redirect to dashboard).
"""
from django.test import TestCase, Client


class SuperAdminRedirectTest(TestCase):
    """Former super-admin paths redirect to /dashboard/."""

    def setUp(self):
        self.client = Client()

    def test_dashboard_super_admin_redirects_to_dashboard(self):
        response = self.client.get("/dashboard/super-admin/", follow=False)
        self.assertEqual(response.status_code, 302)
        self.assertEqual(response.url, "/dashboard/")

    def test_dashboard_super_admin_subpath_redirects_to_dashboard(self):
        response = self.client.get("/dashboard/super-admin/system-control/", follow=False)
        self.assertEqual(response.status_code, 302)
        self.assertEqual(response.url, "/dashboard/")

    def test_super_admin_root_redirects_to_dashboard(self):
        response = self.client.get("/super-admin/", follow=False)
        self.assertEqual(response.status_code, 302)
        self.assertEqual(response.url, "/dashboard/")

    def test_super_admin_subpath_redirects_to_dashboard(self):
        response = self.client.get("/super-admin/emergency/", follow=False)
        self.assertEqual(response.status_code, 302)
        self.assertEqual(response.url, "/dashboard/")
