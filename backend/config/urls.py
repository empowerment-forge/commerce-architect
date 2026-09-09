"""
URL configuration for config project.

The `urlpatterns` list routes URLs to views. For more information please see:
    https://docs.djangoproject.com/en/6.0/topics/http/urls/
Examples:
Function views
    1. Add an import:  from my_app import views
    2. Add a URL to urlpatterns:  path('', views.home, name='home')
Class-based views
    1. Add an import:  from other_app.views import Home
    2. Add a URL to urlpatterns:  path('', Home.as_view(), name='home')
Including another URLconf
    1. Import the include() function: from django.urls import include, path
    2. Add a URL to urlpatterns:  path('blog/', include('blog.urls'))
"""
from django.contrib import admin
from django.urls import path, include
from django.http import HttpResponse
from health.views import health
from django.conf import settings

if settings.COMMERCE_ENV == "development" and settings.MEDIA_STORAGE_BACKEND == "local":
    from media_storage.views import local_media

def root_view(request):
    return HttpResponse("Empowerment Forge Commerce Platform")

urlpatterns = [
    path("", root_view),
    path("health/", health, name="health"),
    path("admin/", admin.site.urls),
    path("api/auth/", include("accounts.urls")),
    path("api/", include("catalog.urls")),
]

if settings.COMMERCE_ENV == "development" and settings.MEDIA_STORAGE_BACKEND == "local":
    urlpatterns.append(path("media/sha256/<str:digest>", local_media, name="local-media"))
