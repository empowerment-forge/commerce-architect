from django.urls import path

from .views import (
    AuthenticatedResendVerificationView,
    ChangeEmailView,
    LogoutView,
    MeView,
    PasswordRecoveryConfirmView,
    PasswordRecoveryRequestView,
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
    path(
        "resend-verification-authenticated/",
        AuthenticatedResendVerificationView.as_view(),
        name="resend_verification_authenticated",
    ),
    path("change-email/", ChangeEmailView.as_view(), name="change_email"),
    path("token/", TokenObtainCookieView.as_view(), name="token_obtain_pair"),
    path("refresh/", TokenRefreshCookieView.as_view(), name="token_refresh"),
    path("logout/", LogoutView.as_view(), name="logout"),
    path("me/", MeView.as_view(), name="me"),
    path(
        "password-reset/request/",
        PasswordRecoveryRequestView.as_view(),
        name="password_reset_request",
    ),
    path(
        "password-reset/confirm/",
        PasswordRecoveryConfirmView.as_view(),
        name="password_reset_confirm",
    ),
]
