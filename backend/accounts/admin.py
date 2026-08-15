from django.contrib import admin
from django.contrib.auth.admin import UserAdmin
from django.contrib.auth.models import User

from .models import AccountSecurityState, EmailVerification, PasswordRecoveryState


admin.site.unregister(User)


@admin.register(User)
class VerificationAwareUserAdmin(UserAdmin):
    readonly_fields = (*UserAdmin.readonly_fields, "email")


@admin.register(EmailVerification)
class EmailVerificationAdmin(admin.ModelAdmin):
    list_display = ("user", "normalized_email", "verified_at", "last_sent_at")
    search_fields = ("user__username", "normalized_email")
    readonly_fields = (
        "id",
        "user",
        "normalized_email",
        "verified_at",
        "token_digest",
        "token_created_at",
        "last_sent_at",
        "created_at",
        "updated_at",
    )

    def has_add_permission(self, request):
        return False

    def has_delete_permission(self, request, obj=None):
        return False


@admin.register(AccountSecurityState)
class AccountSecurityStateAdmin(admin.ModelAdmin):
    list_display = ("user", "session_generation", "updated_at")
    search_fields = ("user__username", "user__email")
    readonly_fields = ("user", "session_generation", "created_at", "updated_at")

    def has_add_permission(self, request):
        return False

    def has_delete_permission(self, request, obj=None):
        return False


@admin.register(PasswordRecoveryState)
class PasswordRecoveryStateAdmin(admin.ModelAdmin):
    list_display = ("user", "normalized_email", "token_created_at", "consumed_at")
    search_fields = ("user__username", "normalized_email")
    readonly_fields = (
        "id",
        "user",
        "normalized_email",
        "token_digest",
        "token_created_at",
        "last_sent_at",
        "consumed_at",
        "created_at",
        "updated_at",
    )

    def has_add_permission(self, request):
        return False

    def has_delete_permission(self, request, obj=None):
        return False
