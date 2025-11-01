from django.contrib import admin
from .models import Project, Sample, Experiment, InventoryItem, UserRole, AuditLog

admin.site.register(Project)
admin.site.register(Sample)
admin.site.register(Experiment)
admin.site.register(InventoryItem)
admin.site.register(UserRole)
admin.site.register(AuditLog)

