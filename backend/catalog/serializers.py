from rest_framework import serializers

from media_storage.configuration import get_media_delivery

from .models import Product


class ProductImageSerializer(serializers.Serializer):
    portable_id = serializers.UUIDField(read_only=True)
    url = serializers.SerializerMethodField()
    alt_text = serializers.CharField(read_only=True)
    sort_order = serializers.IntegerField(read_only=True)
    is_primary = serializers.BooleanField(read_only=True)

    def get_url(self, image):
        return get_media_delivery().public_url(image.storage_key)


class ProductSerializer(serializers.ModelSerializer):
    images = ProductImageSerializer(
        source="presentation_images", many=True, read_only=True
    )

    class Meta:
        model = Product
        fields = [
            "id",
            "name",
            "description",
            "product_type",
            "price",
            "is_active",
            "created_at",
            "images",
        ]
