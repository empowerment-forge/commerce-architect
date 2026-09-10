from django.contrib import admin

from .models import Organization


class OrganizationAdmin(admin.ModelAdmin):
    list_display = ("name", "status", "created_at", "updated_at")
    list_filter = ("status",)
    search_fields = ("name",)
    readonly_fields = ("id", "created_at", "updated_at")

    @staticmethod
    def _is_active_superuser(request):
        user = getattr(request, "user", None)
        return bool(
            user
            and user.is_authenticated
            and user.is_active
            and user.is_superuser
        )

    def has_module_permission(self, request):
        return self._is_active_superuser(request)

    def has_view_permission(self, request, obj=None):
        return self._is_active_superuser(request)

    def has_add_permission(self, request):
        return self._is_active_superuser(request)

    def has_change_permission(self, request, obj=None):
        return self._is_active_superuser(request)

    def has_delete_permission(self, request, obj=None):
        return self._is_active_superuser(request)


admin.site.register(Organization, OrganizationAdmin)
