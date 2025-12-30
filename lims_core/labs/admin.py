from django.contrib import admin
from .models_analysis_context import AnalysisContext


@admin.register(AnalysisContext)
class AnalysisContextAdmin(admin.ModelAdmin):
    list_display = ("code", "name", "laboratory_profile", "is_active")
    list_filter = ("laboratory_profile", "is_active")
    search_fields = ("code", "name")
