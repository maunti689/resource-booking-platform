from datetime import timedelta
from unittest.mock import patch

import pytest
from django.utils import timezone

from apps.bookings.models import Booking, ReminderDelivery
from apps.bookings.tasks import send_upcoming_booking_reminders

pytestmark = [pytest.mark.django_db, pytest.mark.integration]


def test_health_ready_and_request_id(api_client):
    response = api_client.get("/health", HTTP_X_REQUEST_ID="trace-123")
    assert response.status_code == 200
    assert response["X-Request-ID"] == "trace-123"

    response = api_client.get("/ready")
    assert response.status_code == 200
    assert response.json() == {"status": "ready"}


def test_ready_reports_cache_failure(api_client):
    with patch("config.views.cache.get", return_value=None):
        response = api_client.get("/ready")

    assert response.status_code == 503
    assert response.json() == {"status": "not_ready"}


def test_reminder_task_is_idempotent(member_user, resource):
    now = timezone.now()
    Booking.objects.create(
        resource=resource,
        owner=member_user,
        start_at=now + timedelta(minutes=20),
        end_at=now + timedelta(minutes=50),
        purpose="Soon",
    )

    with patch("apps.bookings.tasks.timezone.now", return_value=now):
        first = send_upcoming_booking_reminders()
        second = send_upcoming_booking_reminders()

    assert first == {"delivered": 1}
    assert second == {"delivered": 0}
    assert ReminderDelivery.objects.count() == 1


def test_reminder_does_not_skip_booking_starting_soon(member_user, resource):
    now = timezone.now()
    Booking.objects.create(
        resource=resource,
        owner=member_user,
        start_at=now + timedelta(minutes=5),
        end_at=now + timedelta(minutes=35),
        purpose="Very soon",
    )

    with patch("apps.bookings.tasks.timezone.now", return_value=now):
        result = send_upcoming_booking_reminders()

    assert result == {"delivered": 1}


def test_audit_requires_management(
    client_for, member_user, admin_user, organization, resource, future_window
):
    start_at, end_at = future_window
    Booking.objects.create(
        resource=resource,
        owner=member_user,
        start_at=start_at,
        end_at=end_at,
        purpose="Meeting",
    )

    assert client_for(member_user).get(f"/organizations/{organization.id}/audit").status_code == 403
    assert client_for(admin_user).get(f"/organizations/{organization.id}/audit").status_code == 200
