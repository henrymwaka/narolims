# lims_core/tests/test_write_guardrails.py

from django.test import TestCase
from django.contrib.auth.models import User
from rest_framework.test import APIClient
from rest_framework import status

from lims_core.models import (
    Institute,
    Laboratory,
    Project,
    Sample,
    StaffMember,
    UserRole,
)


class WriteGuardrailTests(TestCase):
    """
    Step 6C tests.

    Guarantees that server-controlled fields cannot be mutated
    after creation, either by validation (400) or permission (403),
    depending on the resource.
    """

    def setUp(self):
        self.client = APIClient()

        # Institute
        self.institute = Institute.objects.create(
            code="INST",
            name="Institute",
        )

        # Laboratories
        self.lab1 = Laboratory.objects.create(
            institute=self.institute,
            code="LAB1",
            name="Lab One",
        )
        self.lab2 = Laboratory.objects.create(
            institute=self.institute,
            code="LAB2",
            name="Lab Two",
        )

        # User
        self.user = User.objects.create_user(
            username="labuser",
            password="pass",
        )

        UserRole.objects.create(
            user=self.user,
            laboratory=self.lab1,
            role="Technician",
        )

        self.client.force_authenticate(user=self.user)

        # Project
        self.project = Project.objects.create(
            name="Project A",
            laboratory=self.lab1,
            created_by=self.user,
        )

        # Sample
        self.sample = Sample.objects.create(
            sample_id="S-001",
            sample_type="DNA",
            laboratory=self.lab1,
            project=self.project,
        )

        # Staff
        self.staff = StaffMember.objects.create(
            full_name="John Doe",
            institute=self.institute,
            laboratory=self.lab1,
            staff_type="EMPLOYEE",
        )

    # ---------------------------------------------------------
    # PROJECT GUARDRAILS
    # ---------------------------------------------------------
    def test_project_laboratory_cannot_be_changed(self):
        payload = {
            "name": "Project A updated",
            "laboratory": self.lab2.id,
        }

        resp = self.client.patch(
            f"/lims/projects/{self.project.id}/",
            payload,
            format="json",
        )

        self.assertEqual(resp.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn("laboratory", resp.data)

    def test_project_created_by_cannot_be_changed(self):
        other_user = User.objects.create_user(
            username="other",
            password="pass",
        )

        payload = {
            "created_by": other_user.id,
        }

        resp = self.client.patch(
            f"/lims/projects/{self.project.id}/",
            payload,
            format="json",
        )

        self.assertEqual(resp.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn("created_by", resp.data)

    # ---------------------------------------------------------
    # SAMPLE GUARDRAILS
    # ---------------------------------------------------------
    def test_sample_project_cannot_be_changed(self):
        payload = {
            "project": self.project.id,
        }

        resp = self.client.patch(
            f"/lims/samples/{self.sample.id}/",
            payload,
            format="json",
        )

        self.assertEqual(resp.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn("project", resp.data)

    def test_sample_laboratory_cannot_be_changed(self):
        payload = {
            "laboratory": self.lab2.id,
        }

        resp = self.client.patch(
            f"/lims/samples/{self.sample.id}/",
            payload,
            format="json",
        )

        self.assertEqual(resp.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn("laboratory", resp.data)

    # ---------------------------------------------------------
    # STAFF GUARDRAILS (permission-level enforcement)
    # ---------------------------------------------------------
    def test_staff_laboratory_cannot_be_changed(self):
        payload = {
            "laboratory": self.lab2.id,
        }

        resp = self.client.patch(
            f"/lims/staff/{self.staff.id}/",
            payload,
            format="json",
        )

        self.assertEqual(resp.status_code, status.HTTP_403_FORBIDDEN)

    def test_staff_institute_cannot_be_changed(self):
        other_inst = Institute.objects.create(
            code="INST2",
            name="Institute Two",
        )

        payload = {
            "institute": other_inst.id,
        }

        resp = self.client.patch(
            f"/lims/staff/{self.staff.id}/",
            payload,
            format="json",
        )

        self.assertEqual(resp.status_code, status.HTTP_403_FORBIDDEN)
