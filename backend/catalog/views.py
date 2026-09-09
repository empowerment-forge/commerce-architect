from rest_framework import generics
from rest_framework.exceptions import APIException

from .services import CatalogNotConfigured, get_storefront_organization, scoped_products
from .serializers import ProductSerializer


class CatalogUnavailable(APIException):
    status_code = 503
    default_detail = "The storefront catalog is not configured."
    default_code = "catalog_not_configured"

# Create your views here.
class ProductListView(generics.ListAPIView):
    serializer_class = ProductSerializer

    def get_queryset(self):
        try:
            organization = get_storefront_organization()
        except CatalogNotConfigured as exc:
            raise CatalogUnavailable() from exc
        return scoped_products(
            organization.pk,
            active_only=True,
            physical_only=True,
        )
