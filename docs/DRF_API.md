# Django REST Framework (DRF) Setup

## Purpose

DRF provides serialization and API transport layer.

------------------------------------------------------------------------

# Installation

Added to requirements.txt and INSTALLED_APPS (in config/settings.py):

    rest_framework

------------------------------------------------------------------------

# Serializer Pattern

Example:

class ProductSerializer(serializers.ModelSerializer): class Meta: model
= Product fields = "**all**"

Responsibilities:

-   Validate input
-   Convert model instances to JSON
-   Control exposed fields

------------------------------------------------------------------------

# View Pattern

Used ListAPIView for product listing.

Principle:

-   Keep views thin
-   Move business rules into models

------------------------------------------------------------------------

# Endpoint

GET /api/products/

Returns JSON response.

Browsable API enabled for development.
