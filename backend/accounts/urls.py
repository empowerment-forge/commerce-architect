from django.urls import path

from .views import (
    ChangeEmailView,
    LogoutView,
    MeView,
    RegisterView,
    ResendVerificationView,
    TokenObtainCookieView,
    TokenRefreshCookieView,
    VerifyEmailView,
)

urlpatterns = [
    path("register/", RegisterView.as_view(), name="register"),
    path("verify-email/", VerifyEmailView.as_view(), name="verify_email"),
    path(
        "resend-verification/",
        ResendVerificationView.as_view(),
        name="resend_verification",
    ),
    path("change-email/", ChangeEmailView.as_view(), name="change_email"),
    path("token/", TokenObtainCookieView.as_view(), name="token_obtain_pair"),
    path("refresh/", TokenRefreshCookieView.as_view(), name="token_refresh"),
    path("logout/", LogoutView.as_view(), name="logout"),
    path("me/", MeView.as_view(), name="me"),
]
