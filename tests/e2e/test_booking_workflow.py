from datetime import timedelta

import pytest

from apps.bookings.models import Booking

pytestmark = [pytest.mark.django_db, pytest.mark.integration]


def test_booking_disappears_from_busy_slots_after_cancellation(
    client_for, member_user, organization, resource, future_window
):
    start_at, end_at = future_window
    client = client_for(member_user)
    availability_url = (
        f"/organizations/{organization.id}/availability"
        f"?date={start_at.date().isoformat()}&duration_minutes=60"
        f"&resource_id={resource.id}"
    )
    initial = client.get(availability_url)
    initial_starts = {slot["start_at"] for slot in initial.data[0]["slots"]}
    expected_start = start_at.isoformat()
    assert expected_start in initial_starts

    booking_response = client.post(
        "/bookings",
        {
            "resource_id": resource.id,
            "start_at": start_at.isoformat(),
            "end_at": end_at.isoformat(),
            "purpose": "Planning",
        },
        format="json",
    )
    assert booking_response.status_code == 201
    busy = client.get(availability_url)
    assert expected_start not in {slot["start_at"] for slot in busy.data[0]["slots"]}

    booking_id = booking_response.data["id"]
    cancel = client.post(f"/bookings/{booking_id}/cancel", {}, format="json")
    assert cancel.status_code == 200
    available_again = client.get(availability_url)
    assert expected_start in {slot["start_at"] for slot in available_again.data[0]["slots"]}


def test_reschedule_rechecks_conflicts(client_for, member_user, peer_user, resource, future_window):
    start_at, end_at = future_window
    first = Booking.objects.create(
        resource=resource,
        owner=member_user,
        start_at=start_at,
        end_at=end_at,
        purpose="First",
    )
    second = Booking.objects.create(
        resource=resource,
        owner=peer_user,
        start_at=start_at + timedelta(hours=2),
        end_at=end_at + timedelta(hours=2),
        purpose="Second",
    )

    response = client_for(peer_user).post(
        f"/bookings/{second.id}/reschedule",
        {
            "start_at": (first.start_at + timedelta(minutes=30)).isoformat(),
            "end_at": (first.end_at + timedelta(minutes=30)).isoformat(),
        },
        format="json",
    )

    assert response.status_code == 409
    second.refresh_from_db()
    assert second.start_at == start_at + timedelta(hours=2)
