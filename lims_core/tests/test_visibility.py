# lims_core/tests/test_visibility.py

from django.test import TestCase
from django.contrib.auth.models import User
from rest_framework.test import APIClient

from lims_core.models import (
    Institute,
    Laboratory,
    StaffMember,
    Project,
    UserRole,
)


class VisibilityTests(TestCase):
    """
    Core visibility and permission guarantees.

    These tests ensure:
    1. Lab isolation works
    2. Institute-level staff visibility works
    3. Superuser global read visibility is allowed
    4. Single-lab users can write without explicit lab context
    """

    def setUp(self):
        self.client = APIClient()

        # Institutes
        self.inst1 = Institute.objects.create(code="INST1", name="Institute One")
        self.inst2 = Institute.objects.create(code="INST2", name="Institute Two")

        # Laboratories
        self.lab1 = Laboratory.objects.create(
            code="LAB1",
            name="Lab One",
            institute=self.inst1,
        )
        self.lab2 = Laboratory.objects.create(
            code="LAB2",
            name="Lab Two",
            institute=self.inst2,
        )

        # Users
        self.user_lab1 = User.objects.create_user(
            username="lab1user",
            password="pass",
        )
        self.user_lab2 = User.objects.create_user(
            username="lab2user",
            password="pass",
        )
        self.superuser = User.objects.create_superuser(
            username="admin",
            password="pass",
            email="admin@test.com",
        )

        # Roles
        UserRole.objects.create(
            user=self.user_lab1,
            laboratory=self.lab1,
            role="Technician",
        )
        UserRole.objects.create(
            user=self.user_lab2,
            laboratory=self.lab2,
            role="Technician",
        )

        # Staff
        StaffMember.objects.create(
            full_name="Lab1 Staff",
            institute=self.inst1,
            laboratory=self.lab1,
            staff_type="EMPLOYEE",
        )

        StaffMember.objects.create(
            full_name="Institute Staff",
            institute=self.inst1,
            laboratory=None,
            staff_type="EMPLOYEE",
        )

        # Projects
        Project.objects.create(
            name="Project Lab1",
            laboratory=self.lab1,
            created_by=self.user_lab1,
        )
        Project.objects.create(
            name="Project Lab2",
            laboratory=self.lab2,
            created_by=self.user_lab2,
        )

    # ---------------------------------------------------------
    # LAB ISOLATION
    # ---------------------------------------------------------
    def test_user_sees_only_own_lab_projects(self):
        self.client.force_authenticate(user=self.user_lab1)

        resp = self.client.get(
            "/lims/projects/",
            {"lab": self.lab1.id},
        )

        self.assertEqual(resp.status_code, 200)
        names = [p["name"] for p in resp.data["results"]]

        self.assertIn("Project Lab1", names)
        self.assertNotIn("Project Lab2", names)

    # ---------------------------------------------------------
    # STAFF VISIBILITY
    # ---------------------------------------------------------
    def test_user_sees_lab_and_institute_staff(self):
        self.client.force_authenticate(user=self.user_lab1)

        resp = self.client.get("/lims/staff/")
        self.assertEqual(resp.status_code, 200)

        names = [s["full_name"] for s in resp.data["results"]]

        self.assertIn("Lab1 Staff", names)
        self.assertIn("Institute Staff", names)

    # ---------------------------------------------------------
    # SUPERUSER VISIBILITY (7B)
    # ---------------------------------------------------------
    def test_superuser_can_read_all_projects_without_lab(self):
        """
        Superusers have global read visibility across laboratories
        without requiring explicit ?lab=.
        """
        self.client.force_authenticate(user=self.superuser)

        resp = self.client.get("/lims/projects/")
        self.assertEqual(resp.status_code, 200)

        names = [p["name"] for p in resp.data["results"]]

        self.assertIn("Project Lab1", names)
        self.assertIn("Project Lab2", names)

    def test_superuser_sees_all_projects_when_lab_is_explicit(self):
        self.client.force_authenticate(user=self.superuser)

        resp1 = self.client.get("/lims/projects/", {"lab": self.lab1.id})
        names1 = [p["name"] for p in resp1.data["results"]]
        self.assertIn("Project Lab1", names1)

        resp2 = self.client.get("/lims/projects/", {"lab": self.lab2.id})
        names2 = [p["name"] for p in resp2.data["results"]]
        self.assertIn("Project Lab2", names2)

    # ---------------------------------------------------------
    # WRITE BEHAVIOR
    # ---------------------------------------------------------
    def test_single_lab_user_can_write_without_explicit_lab(self):
        """
        A user who belongs to exactly one laboratory is allowed to create
        lab-scoped objects without explicitly passing ?lab=.
        """
        self.client.force_authenticate(user=self.user_lab1)

        payload = {
            "name": "Implicit Lab Project",
            "description": "Created without explicit lab parameter",
        }

        resp = self.client.post("/lims/projects/", payload, format="json")

        self.assertEqual(resp.status_code, 201)
        self.assertEqual(resp.data["name"], "Implicit Lab Project")
