# lims_core/tests/test_status_workflows.py

from django.test import TestCase
from django.contrib.auth.models import User
from rest_framework.test import APIClient
from rest_framework import status

from lims_core.models import (
    Institute,
    Laboratory,
    Project,
    Sample,
    Experiment,
    UserRole,
)


class StatusWorkflowTests(TestCase):
    """
    9A: Enforce allowed status transitions
    using the AUTHORITATIVE workflow API.
    """

    def setUp(self):
        self.client = APIClient()

        # --------------------------------------------------
        # Core objects
        # --------------------------------------------------
        self.institute = Institute.objects.create(
            code="INST",
            name="Institute",
        )

        self.lab = Laboratory.objects.create(
            institute=self.institute,
            code="LAB1",
            name="Lab One",
        )

        self.user = User.objects.create_user(
            username="u",
            password="pass",
        )

        UserRole.objects.create(
            user=self.user,
            laboratory=self.lab,
            role="Technician",
        )

        self.client.force_authenticate(user=self.user)

        self.project = Project.objects.create(
            name="Proj",
            laboratory=self.lab,
            created_by=self.user,
        )

        # --------------------------------------------------
        # Workflow-controlled objects
        # --------------------------------------------------
        self.sample = Sample.objects.create(
            sample_id="S-100",
            sample_type="DNA",
            status="REGISTERED",
            laboratory=self.lab,
            project=self.project,
        )

        self.experiment = Experiment.objects.create(
            name="Exp-1",
            status="PLANNED",
            laboratory=self.lab,
            project=self.project,
        )

    # ==================================================
    # SAMPLE WORKFLOW
    # ==================================================

    def test_sample_valid_transition(self):
        """
        REGISTERED -> IN_PROCESS is valid
        """
        resp = self.client.post(
            f"/lims/workflows/sample/{self.sample.id}/transition/",
            {"to_status": "IN_PROCESS"},
            format="json",
        )

        self.assertEqual(resp.status_code, status.HTTP_200_OK)

        self.sample.refresh_from_db()
        self.assertEqual(self.sample.status, "IN_PROCESS")

    def test_sample_invalid_transition(self):
        """
        REGISTERED -> QC_PASSED is invalid
        """
        resp = self.client.post(
            f"/lims/workflows/sample/{self.sample.id}/transition/",
            {"to_status": "QC_PASSED"},
            format="json",
        )

        self.assertEqual(resp.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn("status", resp.data)

        self.sample.refresh_from_db()
        self.assertEqual(self.sample.status, "REGISTERED")

    # ==================================================
    # EXPERIMENT WORKFLOW
    # ==================================================

    def test_experiment_valid_transition(self):
        """
        PLANNED -> RUNNING is valid
        """
        resp = self.client.post(
            f"/lims/workflows/experiment/{self.experiment.id}/transition/",
            {"to_status": "RUNNING"},
            format="json",
        )

        self.assertEqual(resp.status_code, status.HTTP_200_OK)

        self.experiment.refresh_from_db()
        self.assertEqual(self.experiment.status, "RUNNING")

    def test_experiment_invalid_transition(self):
        """
        PLANNED -> COMPLETED is invalid
        """
        resp = self.client.post(
            f"/lims/workflows/experiment/{self.experiment.id}/transition/",
            {"to_status": "COMPLETED"},
            format="json",
        )

        self.assertEqual(resp.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn("status", resp.data)

        self.experiment.refresh_from_db()
        self.assertEqual(self.experiment.status, "PLANNED")
