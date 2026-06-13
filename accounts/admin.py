from django.contrib.auth.admin import UserAdmin as BaseUserAdmin
from accounts.models import User
from leaves.models import WorkerProfile
from django.contrib import admin

class WorkerProfileInline(admin.StackedInline):
    model = WorkerProfile
    can_delete = False
    verbose_name_plural = "Worker"

@admin.register(User)
class UserAdmin(BaseUserAdmin):
    inlines = [WorkerProfileInline]
    list_display = ["username", "role", "is_active", "email"]
    list_filter = ["role", "is_active"]
    search_fields = ["username","email"]
