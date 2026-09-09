from django.contrib import admin
from .models import Product, ProductImage

# Register your models here.
@admin.register(Product)
class ProductAdmin(admin.ModelAdmin):
    list_display = ("name", "product_type", "price", "is_active", "created_at")
    list_filter = ("product_type", "is_active")
    search_fields = ("name",)


@admin.register(ProductImage)
class ProductImageAdmin(admin.ModelAdmin):
    list_display = ("product", "portable_id", "sort_order", "is_primary")
    list_filter = ("is_primary",)
    search_fields = ("storage_key", "alt_text", "product__name")
    readonly_fields = ("portable_id", "created_at", "updated_at")

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
