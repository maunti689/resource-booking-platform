from datetime import timedelta

import pytest

from apps.audit.models import AuditEvent
from apps.bookings.models import Booking, BookingParticipant

pytestmark = [pytest.mark.django_db, pytest.mark.integration]


def booking_payload(resource, future_window, **changes):
    start_at, end_at = future_window
    payload = {
        "resource_id": resource.id,
        "start_at": start_at.isoformat(),
        "end_at": end_at.isoformat(),
        "purpose": "Planning",
        "participants": ["guest@example.com", "guest@example.com"],
    }
    payload.update(changes)
    return payload


def test_create_booking_deduplicates_participants_and_audits(
    client_for, member_user, resource, future_window
):
    response = client_for(member_user).post(
        "/bookings", booking_payload(resource, future_window), format="json"
    )

    assert response.status_code == 201
    assert response.data["owner"] == member_user.username
    assert response.data["participants"] == ["guest@example.com"]
    assert BookingParticipant.objects.count() == 1
    assert AuditEvent.objects.filter(event_type="booking.created").exists()


def test_overlapping_booking_returns_conflict(
    client_for, member_user, peer_user, resource, future_window
):
    client_for(member_user).post(
        "/bookings", booking_payload(resource, future_window), format="json"
    )
    start_at, end_at = future_window
    response = client_for(peer_user).post(
        "/bookings",
        booking_payload(
            resource,
            future_window,
            start_at=(start_at + timedelta(minutes=30)).isoformat(),
            end_at=(end_at + timedelta(minutes=30)).isoformat(),
        ),
        format="json",
    )

    assert response.status_code == 409
    assert response.data["error"]["code"] == "conflict"
    assert Booking.objects.count() == 1


def test_booking_is_hidden_from_other_tenant(
    client_for, member_user, outsider_user, resource, future_window
):
    create_response = client_for(member_user).post(
        "/bookings", booking_payload(resource, future_window), format="json"
    )

    response = client_for(outsider_user).get(f"/bookings/{create_response.data['id']}")
    assert response.status_code == 404

    list_response = client_for(outsider_user).get(
        f"/bookings?organization_id={resource.organization_id}"
    )
    assert list_response.status_code == 404
    start_at, end_at = future_window
    update_response = client_for(outsider_user).post(
        f"/bookings/{create_response.data['id']}/reschedule",
        {
            "start_at": (start_at + timedelta(hours=2)).isoformat(),
            "end_at": (end_at + timedelta(hours=2)).isoformat(),
        },
        format="json",
    )
    assert update_response.status_code == 404


def test_organization_duration_limit_applies_to_booking_and_search(
    client_for, member_user, organization, resource, future_window
):
    organization.max_booking_duration_minutes = 30
    organization.save(update_fields=["max_booking_duration_minutes"])
    client = client_for(member_user)

    booking_response = client.post(
        "/bookings", booking_payload(resource, future_window), format="json"
    )
    availability_response = client.get(
        f"/organizations/{organization.id}/availability"
        f"?date={future_window[0].date().isoformat()}&duration_minutes=60"
    )

    assert booking_response.status_code == 422
    assert availability_response.status_code == 422


def test_owner_can_reschedule_and_cancel(client_for, member_user, resource, future_window):
    client = client_for(member_user)
    create_response = client.post(
        "/bookings", booking_payload(resource, future_window), format="json"
    )
    booking_id = create_response.data["id"]
    start_at, end_at = future_window

    response = client.post(
        f"/bookings/{booking_id}/reschedule",
        {
            "start_at": (start_at + timedelta(hours=2)).isoformat(),
            "end_at": (end_at + timedelta(hours=2)).isoformat(),
        },
        format="json",
    )
    assert response.status_code == 200

    response = client.post(
        f"/bookings/{booking_id}/cancel", {"reason": "Changed plans"}, format="json"
    )
    assert response.status_code == 200
    assert response.data["status"] == Booking.Status.CANCELLED
    assert response.data["cancel_reason"] == "Changed plans"


def test_peer_cannot_reschedule_or_cancel(
    client_for, member_user, peer_user, resource, future_window
):
    booking_id = (
        client_for(member_user)
        .post("/bookings", booking_payload(resource, future_window), format="json")
        .data["id"]
    )
    start_at, end_at = future_window
    peer_client = client_for(peer_user)

    reschedule = peer_client.post(
        f"/bookings/{booking_id}/reschedule",
        {
            "start_at": (start_at + timedelta(hours=2)).isoformat(),
            "end_at": (end_at + timedelta(hours=2)).isoformat(),
        },
        format="json",
    )
    cancel = peer_client.post(f"/bookings/{booking_id}/cancel", {"reason": "No"}, format="json")

    assert reschedule.status_code == 403
    assert cancel.status_code == 403


def test_manager_override_requires_reason_and_is_audited(
    client_for, member_user, manager_user, resource, future_window
):
    booking_id = (
        client_for(member_user)
        .post("/bookings", booking_payload(resource, future_window), format="json")
        .data["id"]
    )
    manager_client = client_for(manager_user)

    invalid = manager_client.post(
        f"/bookings/{booking_id}/override-cancel", {"reason": ""}, format="json"
    )
    assert invalid.status_code == 400

    response = manager_client.post(
        f"/bookings/{booking_id}/override-cancel",
        {"reason": "Emergency maintenance"},
        format="json",
    )
    assert response.status_code == 200
    assert AuditEvent.objects.filter(event_type="booking.override_cancelled").exists()


def test_my_schedule_includes_participant_booking(
    client_for, admin_user, member_user, resource, future_window
):
    client_for(admin_user).post(
        "/bookings",
        booking_payload(
            resource,
            future_window,
            participants=[member_user.email],
        ),
        format="json",
    )

    response = client_for(member_user).get("/me/schedule")
    assert response.status_code == 200
    assert len(response.data) == 1


def test_booking_list_filters_by_organization_and_status(
    client_for, member_user, organization, resource, future_window
):
    client = client_for(member_user)
    booking_id = client.post(
        "/bookings", booking_payload(resource, future_window), format="json"
    ).data["id"]
    client.post(f"/bookings/{booking_id}/cancel", {}, format="json")

    response = client.get(f"/bookings?organization_id={organization.id}&status=cancelled")
    assert response.status_code == 200
    assert [item["id"] for item in response.data] == [booking_id]


def test_cancelled_booking_cannot_be_cancelled_twice(
    client_for, member_user, resource, future_window
):
    client = client_for(member_user)
    booking_id = client.post(
        "/bookings", booking_payload(resource, future_window), format="json"
    ).data["id"]
    client.post(f"/bookings/{booking_id}/cancel", {}, format="json")

    response = client.post(f"/bookings/{booking_id}/cancel", {}, format="json")
    assert response.status_code == 409
