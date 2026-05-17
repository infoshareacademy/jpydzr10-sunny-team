from django.contrib import admin
from leaves.models import LeaveRequest


def approve_selected(modeladmin, request, queryset):
    queryset.update(status="approved")

approve_selected.short_description = "Zatwierdź zaznaczone wnioski"


@admin.register(LeaveRequest)
class LeaveRequestAdmin(admin.ModelAdmin):
    list_display = ["employee", "start_date","end_date","amount_days","status"]
    list_filter = ["status", "employee", "who_confirmed","created_at","updated_at"]
    date_hierarchy = "start_date"
    actions = [approve_selected]
