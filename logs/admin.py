from django.contrib import admin
from logs.models import ActivityLog


@admin.register(ActivityLog)
class ChangeLogAdmin(admin.ModelAdmin):
    readonly_fields = ["who","action","object_type","created_at"]
    def has_add_permission(self,request):
        return False

    def has_change_permission(self,request,obj = None):
        return False