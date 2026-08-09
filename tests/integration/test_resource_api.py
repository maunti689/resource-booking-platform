from datetime import datetime, time, timedelta, timezone

import pytest

from apps.audit.models import AuditEvent
from apps.resources.models import AvailabilityRule, BlackoutPeriod, Resource

pytestmark = [pytest.mark.django_db, pytest.mark.integration]


def test_manager_can_create_and_update_resource(client_for, manager_user, organization):
    client = client_for(manager_user)
    response = client.post(
        f"/organizations/{organization.id}/resources",
        {
            "name": "Projector",
            "resource_type": "equipment",
            "capacity": 2,
            "timezone": "Europe/Moscow",
        },
    )
    assert response.status_code == 201

    resource_id = response.data["id"]
    response = client.patch(
        f"/organizations/{organization.id}/resources/{resource_id}",
        {"capacity": 3},
    )
    assert response.status_code == 200
    assert response.data["capacity"] == 3
    assert response.data["availability_version"] == 2


def test_member_cannot_create_resource(client_for, member_user, organization):
    response = client_for(member_user).post(
        f"/organizations/{organization.id}/resources",
        {"name": "Room B", "capacity": 4, "timezone": "UTC"},
    )

    assert response.status_code == 403


def test_invalid_timezone_returns_domain_error(client_for, admin_user, organization):
    response = client_for(admin_user).post(
        f"/organizations/{organization.id}/resources",
        {"name": "Room B", "capacity": 4, "timezone": "Mars/Olympus"},
    )

    assert response.status_code == 422
    assert response.data["error"]["code"] == "domain_validation_failed"


def test_resource_is_hidden_from_other_tenant(client_for, outsider_user, organization, resource):
    response = client_for(outsider_user).get(
        f"/organizations/{organization.id}/resources/{resource.id}"
    )

    assert response.status_code == 404

    list_response = client_for(outsider_user).get(f"/organizations/{organization.id}/resources")
    update_response = client_for(outsider_user).patch(
        f"/organizations/{organization.id}/resources/{resource.id}",
        {"capacity": 99},
    )
    assert list_response.status_code == 404
    assert update_response.status_code == 404


def test_manager_can_archive_resource_but_member_cannot(
    client_for, manager_user, member_user, organization, resource
):
    url = f"/organizations/{organization.id}/resources/{resource.id}"
    assert client_for(member_user).patch(url, {"capacity": 99}).status_code == 403
    assert client_for(member_user).delete(url).status_code == 403

    manager_client = client_for(manager_user)
    assert manager_client.delete(url).status_code == 204
    assert manager_client.delete(url).status_code == 204
    resource.refresh_from_db()
    assert resource.is_active is False
    assert (
        AuditEvent.objects.filter(
            event_type="resource.archived", object_id=str(resource.id)
        ).count()
        == 1
    )


def test_availability_rule_is_upserted_and_versioned(
    client_for, manager_user, organization, resource
):
    response = client_for(manager_user).post(
        f"/organizations/{organization.id}/resources/{resource.id}/availability-rules",
        {"weekday": 0, "start_time": "08:00", "end_time": "17:00"},
    )

    assert response.status_code == 201
    assert AvailabilityRule.objects.filter(resource=resource, weekday=0).count() == 1
    resource.refresh_from_db()
    assert resource.availability_version == 2


def test_blackout_rejects_foreign_resource(
    client_for, admin_user, organization, second_resource, future_window
):
    start_at, end_at = future_window
    response = client_for(admin_user).post(
        f"/organizations/{organization.id}/blackouts",
        {
            "resource_id": second_resource.id,
            "start_at": start_at.isoformat(),
            "end_at": end_at.isoformat(),
            "reason": "Not ours",
        },
    )

    assert response.status_code == 404
    assert BlackoutPeriod.objects.count() == 0


def test_availability_filters_capacity_and_busy_slots(
    client_for, member_user, admin_user, organization, resource, future_window
):
    from apps.bookings.models import Booking

    start_at, end_at = future_window
    Booking.objects.create(
        resource=resource,
        owner=member_user,
        start_at=start_at,
        end_at=end_at,
        purpose="Busy",
    )
    client = client_for(member_user)
    url = (
        f"/organizations/{organization.id}/availability"
        f"?date={start_at.date().isoformat()}&duration_minutes=60&capacity=8"
    )
    response = client.get(url)

    assert response.status_code == 200
    slots = response.data[0]["slots"]
    assert start_at.isoformat() not in {slot["start_at"] for slot in slots}

    too_large = client.get(f"{url[:-1]}9")
    assert too_large.status_code == 200
    assert too_large.data == []


def test_availability_query_count_does_not_grow_per_resource(
    client_for,
    member_user,
    organization,
    resource,
    future_window,
    django_assert_num_queries,
):
    start_at, _ = future_window
    for index in range(3):
        extra_resource = Resource.objects.create(
            organization=organization,
            name=f"Room {index}",
            capacity=4,
            timezone="UTC",
        )
        AvailabilityRule.objects.create(
            resource=extra_resource,
            weekday=start_at.weekday(),
            start_time=time(9, 0),
            end_time=time(18, 0),
        )

    url = (
        f"/organizations/{organization.id}/availability"
        f"?date={start_at.date().isoformat()}&duration_minutes=60"
    )
    client = client_for(member_user)
    with django_assert_num_queries(6):
        response = client.get(url)
    assert response.status_code == 200
    assert len(response.data) == 4

    with django_assert_num_queries(3):
        cached_response = client.get(url)
    assert cached_response.status_code == 200


def test_timezone_rules_are_converted_to_utc(client_for, member_user, organization, future_window):
    target_date = future_window[0].date()
    resource = Resource.objects.create(
        organization=organization,
        name="Moscow Room",
        capacity=4,
        timezone="Europe/Moscow",
    )
    AvailabilityRule.objects.create(
        resource=resource,
        weekday=target_date.weekday(),
        start_time=time(9, 0),
        end_time=time(11, 0),
    )
    expected_start = datetime.combine(target_date, time(6, 0), tzinfo=timezone.utc)
    expected_end = expected_start + timedelta(hours=1)
    client = client_for(member_user)

    availability = client.get(
        f"/organizations/{organization.id}/availability"
        f"?date={target_date.isoformat()}&duration_minutes=60"
        f"&resource_id={resource.id}"
    )
    assert availability.status_code == 200
    assert availability.data[0]["slots"][0]["start_at"] == expected_start.isoformat()

    booking = client.post(
        "/bookings",
        {
            "resource_id": resource.id,
            "start_at": expected_start.isoformat(),
            "end_at": expected_end.isoformat(),
            "purpose": "Local morning",
        },
        format="json",
    )
    assert booking.status_code == 201
    assert booking.data["resource_timezone"] == "Europe/Moscow"


def test_blackout_creation_invalidates_availability_version(
    client_for, manager_user, organization, resource, future_window
):
    start_at, end_at = future_window
    response = client_for(manager_user).post(
        f"/organizations/{organization.id}/blackouts",
        {
            "resource_id": resource.id,
            "start_at": (start_at + timedelta(hours=2)).isoformat(),
            "end_at": (end_at + timedelta(hours=2)).isoformat(),
            "reason": "Maintenance",
        },
    )

    assert response.status_code == 201
    resource.refresh_from_db()
    assert resource.availability_version == 2
