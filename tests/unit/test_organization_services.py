import pytest
from rest_framework.exceptions import NotFound, PermissionDenied

from apps.organizations.models import Membership
from apps.organizations.services import (
    add_member,
    membership_for,
    remove_member,
    update_member_role,
)

pytestmark = pytest.mark.django_db


def test_non_member_cannot_resolve_organization(outsider_user, organization):
    with pytest.raises(NotFound):
        membership_for(outsider_user, organization)


def test_only_admin_can_add_member(manager_user, outsider_user, organization):
    with pytest.raises(PermissionDenied):
        add_member(
            actor=manager_user,
            organization=organization,
            username=outsider_user.username,
            role=Membership.Role.MEMBER,
        )


def test_admin_cannot_demote_or_remove_self(admin_user, organization):
    membership = membership_for(admin_user, organization)

    with pytest.raises(PermissionDenied):
        update_member_role(
            actor=admin_user,
            organization=organization,
            membership=membership,
            role=Membership.Role.MEMBER,
        )
    with pytest.raises(PermissionDenied):
        remove_member(actor=admin_user, organization=organization, membership=membership)


def test_membership_from_another_tenant_is_hidden(
    admin_user, organization, outsider_user, second_organization
):
    foreign_membership = membership_for(outsider_user, second_organization)

    with pytest.raises(NotFound):
        update_member_role(
            actor=admin_user,
            organization=organization,
            membership=foreign_membership,
            role=Membership.Role.MANAGER,
        )
