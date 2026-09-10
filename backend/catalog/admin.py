from django.contrib import admin
from django.core.exceptions import ValidationError
from .models import Product, ProductImage
from .services import (
    CatalogNotConfigured,
    catalog_write_lock,
    get_storefront_organization,
)

# Register your models here.
@admin.register(Product)
class ProductAdmin(admin.ModelAdmin):
    list_display = ("name", "product_type", "price", "is_active", "created_at")
    list_filter = ("product_type", "is_active")
    search_fields = ("name",)
    actions = ()

    def get_queryset(self, request):
        try:
            organization = get_storefront_organization()
        except CatalogNotConfigured:
            return self.model.objects.none()
        return super().get_queryset(request).filter(
            organization_id=organization.pk,
            product_type="physical",
        )

    def save_model(self, request, obj, form, change):
        try:
            organization = get_storefront_organization()
        except CatalogNotConfigured as exc:
            raise ValidationError("The storefront Organization is not configured.") from exc
        if obj.organization_id != organization.pk:
            raise ValidationError("Product must belong to the configured Organization.")
        with catalog_write_lock(organization.pk):
            super().save_model(request, obj, form, change)

    def has_delete_permission(self, request, obj=None):
        return False


@admin.register(ProductImage)
class ProductImageAdmin(admin.ModelAdmin):
    list_display = ("product", "portable_id", "sort_order", "is_primary")
    list_filter = ("is_primary",)
    search_fields = ("storage_key", "alt_text", "product__name")
    readonly_fields = ("portable_id", "storage_key", "created_at", "updated_at")
    actions = ()

    def get_queryset(self, request):
        try:
            organization = get_storefront_organization()
        except CatalogNotConfigured:
            return self.model.objects.none()
        return super().get_queryset(request).filter(
            product__organization_id=organization.pk
        )

    def save_model(self, request, obj, form, change):
        try:
            organization = get_storefront_organization()
        except CatalogNotConfigured as exc:
            raise ValidationError("The storefront Organization is not configured.") from exc
        if obj.product.organization_id != organization.pk:
            raise ValidationError("Image must belong to the configured Organization.")
        with catalog_write_lock(organization.pk):
            super().save_model(request, obj, form, change)

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
        return False

    def has_change_permission(self, request, obj=None):
        return self._is_active_superuser(request)

    def has_delete_permission(self, request, obj=None):
        return self._is_active_superuser(request)

    def delete_model(self, request, obj):
        with catalog_write_lock(obj.product.organization_id):
            super().delete_model(request, obj)
