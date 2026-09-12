"""Fixed, code-owned Organization operator permission policy."""

from types import MappingProxyType

from .models import OrganizationMembership


ORGANIZATION_VIEW = "organization.view"
ORGANIZATION_SETTINGS_VIEW = "organization.settings.view"
ORGANIZATION_SETTINGS_EDIT = "organization.settings.edit"
ORGANIZATION_MEMBERS_VIEW = "organization.members.view"
ORGANIZATION_MEMBERS_INVITE = "organization.members.invite"
ORGANIZATION_MEMBERS_MANAGE = "organization.members.manage"
ORGANIZATION_MEMBERS_LEAVE = "organization.members.leave"
ORGANIZATION_ADMINISTRATORS_MANAGE = "organization.administrators.manage"
ORGANIZATION_OWNERSHIP_MANAGE = "organization.ownership.manage"
ORGANIZATION_CAPABILITIES_VIEW = "organization.capabilities.view"
ORGANIZATION_CAPABILITIES_MANAGE = "organization.capabilities.manage"
PRODUCTS_VIEW = "product_commerce.products.view"
PRODUCTS_EDIT = "product_commerce.products.edit"
IMAGES_MANAGE = "product_commerce.images.manage"
PRESENTATION_MANAGE = "product_commerce.presentation.manage"

ALL_PERMISSIONS = frozenset(
    {
        ORGANIZATION_VIEW,
        ORGANIZATION_SETTINGS_VIEW,
        ORGANIZATION_SETTINGS_EDIT,
        ORGANIZATION_MEMBERS_VIEW,
        ORGANIZATION_MEMBERS_INVITE,
        ORGANIZATION_MEMBERS_MANAGE,
        ORGANIZATION_MEMBERS_LEAVE,
        ORGANIZATION_ADMINISTRATORS_MANAGE,
        ORGANIZATION_OWNERSHIP_MANAGE,
        ORGANIZATION_CAPABILITIES_VIEW,
        ORGANIZATION_CAPABILITIES_MANAGE,
        PRODUCTS_VIEW,
        PRODUCTS_EDIT,
        IMAGES_MANAGE,
        PRESENTATION_MANAGE,
    }
)


ROLE_PERMISSIONS = MappingProxyType(
    {
        OrganizationMembership.ROLE_OWNER: frozenset(ALL_PERMISSIONS),
        OrganizationMembership.ROLE_ADMINISTRATOR: frozenset(
            {
                ORGANIZATION_VIEW,
                ORGANIZATION_SETTINGS_VIEW,
                ORGANIZATION_SETTINGS_EDIT,
                ORGANIZATION_MEMBERS_VIEW,
                ORGANIZATION_MEMBERS_INVITE,
                ORGANIZATION_MEMBERS_MANAGE,
                ORGANIZATION_MEMBERS_LEAVE,
                ORGANIZATION_CAPABILITIES_VIEW,
                ORGANIZATION_CAPABILITIES_MANAGE,
                PRODUCTS_VIEW,
                PRODUCTS_EDIT,
                IMAGES_MANAGE,
                PRESENTATION_MANAGE,
            }
        ),
        OrganizationMembership.ROLE_MANAGER: frozenset(
            {
                ORGANIZATION_VIEW,
                ORGANIZATION_MEMBERS_LEAVE,
                PRODUCTS_VIEW,
                PRODUCTS_EDIT,
                IMAGES_MANAGE,
            }
        ),
        OrganizationMembership.ROLE_STAFF: frozenset(
            {ORGANIZATION_VIEW, ORGANIZATION_MEMBERS_LEAVE, PRODUCTS_VIEW}
        ),
    }
)


def permissions_for_role(role):
    """Return an immutable grant set, or an empty set for an unknown role."""
    return ROLE_PERMISSIONS.get(role, frozenset())


def has_permission(role, permission):
    """Fail closed for unknown roles and permission identifiers."""
    return permission in permissions_for_role(role)
