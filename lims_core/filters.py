# lims_core/filters.py
import django_filters as df
from .models import Project, Sample, Experiment, InventoryItem


class ProjectFilter(df.FilterSet):
    name = df.CharFilter(field_name="name", lookup_expr="icontains")
    start_date = df.DateFromToRangeFilter()
    end_date = df.DateFromToRangeFilter()

    class Meta:
        model = Project
        fields = ["name", "start_date", "end_date", "created_by"]


class SampleFilter(df.FilterSet):
    project = df.NumberFilter(field_name="project_id")
    sample_id = df.CharFilter(field_name="sample_id", lookup_expr="icontains")
    sample_type = df.CharFilter(field_name="sample_type", lookup_expr="icontains")
    collected_on = df.DateFromToRangeFilter()

    class Meta:
        model = Sample
        fields = ["project", "sample_id", "sample_type", "collected_on", "storage_location"]


class ExperimentFilter(df.FilterSet):
    project = df.NumberFilter(field_name="project_id")
    name = df.CharFilter(field_name="name", lookup_expr="icontains")
    start_date = df.DateFromToRangeFilter()
    end_date = df.DateFromToRangeFilter()

    class Meta:
        model = Experiment
        fields = ["project", "name", "start_date", "end_date"]


class InventoryItemFilter(df.FilterSet):
    name = df.CharFilter(field_name="name", lookup_expr="icontains")
    category = df.CharFilter(field_name="category", lookup_expr="icontains")
    supplier = df.CharFilter(field_name="supplier", lookup_expr="icontains")
    expiry_date = df.DateFromToRangeFilter()

    class Meta:
        model = InventoryItem
        fields = ["name", "category", "supplier", "expiry_date", "location"]
