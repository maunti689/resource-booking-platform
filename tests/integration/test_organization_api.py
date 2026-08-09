import pytest

from apps.organizations.models import Membership, Organization

pytestmark = [pytest.mark.django_db, pytest.mark.integration]


def test_authentication_and_jwt(api_client, admin_user):
    response = api_client.get("/organizations")
    assert response.status_code == 401

    response = api_client.post(
        "/auth/token", {"username": admin_user.username, "password": "password"}
    )
    assert response.status_code == 200
    assert {"access", "refresh"} <= response.data.keys()


def test_create_organization_makes_actor_admin(client_for, outsider_user):
    response = client_for(outsider_user).post(
        "/organizations",
        {
            "name": "Clinic",
            "slug": "clinic",
            "max_booking_duration_minutes": 90,
        },
    )

    assert response.status_code == 201
    organization = Organization.objects.get(slug="clinic")
    assert organization.memberships.get(user=outsider_user).role == Membership.Role.ADMIN
    assert organization.max_booking_duration_minutes == 90


def test_organization_list_is_tenant_scoped(
    client_for, member_user, organization, second_organization
):
    response = client_for(member_user).get("/organizations")

    assert response.status_code == 200
    assert [item["id"] for item in response.data] == [organization.id]


def test_only_admin_can_update_organization_settings(
    client_for, admin_user, member_user, organization
):
    url = f"/organizations/{organization.id}"
    forbidden = client_for(member_user).patch(url, {"max_booking_duration_minutes": 60})
    assert forbidden.status_code == 403

    response = client_for(admin_user).patch(url, {"max_booking_duration_minutes": 60})
    assert response.status_code == 200
    assert response.data["max_booking_duration_minutes"] == 60


def test_admin_can_manage_members(client_for, admin_user, outsider_user, organization):
    client = client_for(admin_user)
    create_response = client.post(
        f"/organizations/{organization.id}/members",
        {"username": outsider_user.username, "role": Membership.Role.MEMBER},
    )
    assert create_response.status_code == 201

    membership_id = create_response.data["id"]
    update_response = client.patch(
        f"/organizations/{organization.id}/members/{membership_id}",
        {"role": Membership.Role.MANAGER},
    )
    assert update_response.status_code == 200
    assert update_response.data["role"] == Membership.Role.MANAGER

    delete_response = client.delete(f"/organizations/{organization.id}/members/{membership_id}")
    assert delete_response.status_code == 204
    assert not Membership.objects.filter(pk=membership_id).exists()


def test_member_cannot_manage_members(client_for, member_user, outsider_user, organization):
    response = client_for(member_user).post(
        f"/organizations/{organization.id}/members",
        {"username": outsider_user.username, "role": Membership.Role.MEMBER},
    )

    assert response.status_code == 403
    assert response.data["error"]["code"] == "permission_denied"


def test_existing_member_cannot_be_added_again(client_for, admin_user, organization):
    response = client_for(admin_user).post(
        f"/organizations/{organization.id}/members",
        {"username": admin_user.username, "role": Membership.Role.MEMBER},
    )

    assert response.status_code == 409
    assert (
        Membership.objects.get(organization=organization, user=admin_user).role
        == Membership.Role.ADMIN
    )


def test_cross_tenant_membership_is_not_found(
    client_for, admin_user, organization, outsider_user, second_organization
):
    membership = Membership.objects.get(organization=second_organization, user=outsider_user)
    response = client_for(admin_user).patch(
        f"/organizations/{organization.id}/members/{membership.id}",
        {"role": Membership.Role.MEMBER},
    )

    assert response.status_code == 404
