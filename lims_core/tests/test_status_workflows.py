# lims_core/tests/test_status_workflows.py

from django.test import TestCase
from django.contrib.auth.models import User
from rest_framework.test import APIClient
from rest_framework import status

from lims_core.models import Institute, Laboratory, Project, Sample, Experiment, UserRole


class StatusWorkflowTests(TestCase):
    """
    9A: Enforce allowed status transitions.
    """

    def setUp(self):
        self.client = APIClient()

        self.institute = Institute.objects.create(code="INST", name="Institute")
        self.lab = Laboratory.objects.create(institute=self.institute, code="LAB1", name="Lab One")

        self.user = User.objects.create_user(username="u", password="pass")
        UserRole.objects.create(user=self.user, laboratory=self.lab, role="Technician")

        self.client.force_authenticate(user=self.user)

        self.project = Project.objects.create(
            name="Proj",
            laboratory=self.lab,
            created_by=self.user,
        )

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

    def test_sample_valid_transition(self):
        resp = self.client.patch(
            f"/lims/samples/{self.sample.id}/",
            {"status": "IN_PROCESS"},
            format="json",
        )
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp.data["status"], "IN_PROCESS")

    def test_sample_invalid_transition(self):
        # REGISTERED -> QC_PASSED is illegal
        resp = self.client.patch(
            f"/lims/samples/{self.sample.id}/",
            {"status": "QC_PASSED"},
            format="json",
        )
        self.assertEqual(resp.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn("status", resp.data)

    def test_experiment_valid_transition(self):
        resp = self.client.patch(
            f"/lims/experiments/{self.experiment.id}/",
            {"status": "RUNNING"},
            format="json",
        )
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp.data["status"], "RUNNING")

    def test_experiment_invalid_transition(self):
        # PLANNED -> COMPLETED is illegal
        resp = self.client.patch(
            f"/lims/experiments/{self.experiment.id}/",
            {"status": "COMPLETED"},
            format="json",
        )
        self.assertEqual(resp.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn("status", resp.data)
