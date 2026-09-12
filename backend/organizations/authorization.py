"""Reusable request-scoped operator authorization policy."""

from dataclasses import dataclass

from accounts.models import AccountSecurityState
from accounts.services import is_verified
from django.contrib.auth import get_user_model

from .models import Organization, OrganizationMembership
from .permissions import permissions_for_role


class OperatorAuthorizationDenied(PermissionError):
    """Raised for every failed operator authorization decision."""

    code = "OPERATOR_NOT_AUTHORIZED"


@dataclass(frozen=True)
class OperatorAuthorizationContext:
    organization: Organization
    membership: OrganizationMembership
    role: str
    permissions: frozenset[str]


def _deny():
    raise OperatorAuthorizationDenied


def _explicit_organization_id(value):
    if isinstance(value, bool) or not isinstance(value, int) or value <= 0:
        _deny()
    return value


def _token_generation(request, user):
    auth = getattr(request, "auth", None)
    if auth is None or not hasattr(auth, "get"):
        _deny()
    if auth.get("token_type") != "access":
        _deny()
    token_user_id = auth.get("user_id")
    if token_user_id is not None and str(token_user_id) != str(user.pk):
        _deny()
    generation = auth.get("session_generation", 0)
    if isinstance(generation, bool) or not isinstance(generation, int) or generation < 0:
        _deny()
    current_generation = (
        AccountSecurityState.objects.filter(user_id=user.pk)
        .values_list("session_generation", flat=True)
        .first()
    )
    if current_generation is None:
        current_generation = 0
    if generation != current_generation:
        _deny()


def resolve_operator_authorization(request, organization_id, permission):
    """Resolve one exact permission for the explicitly selected Organization.

    ``request.auth`` must be the validated access token. This policy does not
    trust JWT expiry alone and never uses the configured storefront scope.
    """
    user = getattr(request, "user", None)
    if user is None or not getattr(user, "is_authenticated", False):
        _deny()
    user = get_user_model().objects.filter(pk=user.pk).first()
    if user is None:
        _deny()
    if not user.is_active or not is_verified(user):
        _deny()
    _token_generation(request, user)

    organization_id = _explicit_organization_id(organization_id)
    try:
        organization = Organization.objects.get(
            pk=organization_id,
            status=Organization.STATUS_ACTIVE,
        )
    except Organization.DoesNotExist:
        _deny()

    membership = (
        OrganizationMembership.objects.select_related("organization", "user")
        .filter(
            organization_id=organization.pk,
            user_id=user.pk,
            status=OrganizationMembership.STATUS_ACTIVE,
        )
        .first()
    )
    if membership is None:
        _deny()

    if not OrganizationMembership.objects.filter(
        organization_id=organization.pk,
        role=OrganizationMembership.ROLE_OWNER,
        status=OrganizationMembership.STATUS_ACTIVE,
        user__is_active=True,
    ).exists():
        _deny()

    permissions = permissions_for_role(membership.role)
    if not isinstance(permission, str) or permission not in permissions:
        _deny()
    return OperatorAuthorizationContext(
        organization=organization,
        membership=membership,
        role=membership.role,
        permissions=permissions,
    )
