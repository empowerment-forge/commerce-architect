from django.urls import path

from .views import (
    LogoutView,
    MeView,
    RegisterView,
    TokenObtainCookieView,
    TokenRefreshCookieView,
)

urlpatterns = [
    path("register/", RegisterView.as_view(), name="register"),
    path("token/", TokenObtainCookieView.as_view(), name="token_obtain_pair"),
    path("refresh/", TokenRefreshCookieView.as_view(), name="token_refresh"),
    path("logout/", LogoutView.as_view(), name="logout"),
    path("me/", MeView.as_view(), name="me"),
]
