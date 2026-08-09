from datetime import timedelta

import pytest
from rest_framework.exceptions import PermissionDenied

from apps.bookings.models import Booking
from apps.bookings.services import cancel_booking, create_booking, reschedule_booking
from apps.resources.models import BlackoutPeriod
from config.exceptions import ConflictError, DomainValidationError

pytestmark = pytest.mark.django_db


def create_default_booking(member_user, resource, future_window):
    start_at, end_at = future_window
    return create_booking(
        actor=member_user,
        resource=resource,
        start_at=start_at,
        end_at=end_at,
        purpose="Planning",
        participant_emails=[],
    )


def test_overlapping_booking_is_rejected(member_user, peer_user, resource, future_window):
    booking = create_default_booking(member_user, resource, future_window)

    with pytest.raises(ConflictError):
        create_booking(
            actor=peer_user,
            resource=resource,
            start_at=booking.start_at + timedelta(minutes=30),
            end_at=booking.end_at + timedelta(minutes=30),
            purpose="Conflict",
            participant_emails=[],
        )


def test_adjacent_booking_is_allowed(member_user, peer_user, resource, future_window):
    booking = create_default_booking(member_user, resource, future_window)

    adjacent = create_booking(
        actor=peer_user,
        resource=resource,
        start_at=booking.end_at,
        end_at=booking.end_at + timedelta(hours=1),
        purpose="Next meeting",
        participant_emails=[],
    )

    assert adjacent.status == Booking.Status.CONFIRMED


@pytest.mark.parametrize(
    ("start_delta", "end_delta"),
    [
        (timedelta(hours=-3), timedelta(hours=-2)),
        (timedelta(), timedelta(hours=9)),
        (timedelta(), timedelta(days=1)),
    ],
)
def test_invalid_booking_windows_are_rejected(
    member_user, resource, future_window, start_delta, end_delta
):
    start_at, end_at = future_window

    with pytest.raises(DomainValidationError):
        create_booking(
            actor=member_user,
            resource=resource,
            start_at=start_at + start_delta,
            end_at=end_at + end_delta,
            purpose="Invalid",
            participant_emails=[],
        )


def test_blackout_blocks_booking(admin_user, member_user, resource, future_window):
    start_at, end_at = future_window
    BlackoutPeriod.objects.create(
        resource=resource,
        start_at=start_at,
        end_at=end_at,
        reason="Maintenance",
        created_by=admin_user,
    )

    with pytest.raises(ConflictError):
        create_default_booking(member_user, resource, future_window)


def test_inactive_resource_cannot_be_booked(member_user, resource, future_window):
    resource.is_active = False
    resource.save(update_fields=["is_active"])

    with pytest.raises(DomainValidationError):
        create_default_booking(member_user, resource, future_window)


def test_booking_duration_uses_organization_limit(
    member_user, organization, resource, future_window
):
    organization.max_booking_duration_minutes = 30
    organization.save(update_fields=["max_booking_duration_minutes"])

    with pytest.raises(DomainValidationError):
        create_default_booking(member_user, resource, future_window)


def test_only_owner_or_management_can_change_booking(
    member_user, peer_user, resource, future_window
):
    booking = create_default_booking(member_user, resource, future_window)
    start_at, end_at = future_window

    with pytest.raises(PermissionDenied):
        reschedule_booking(
            actor=peer_user,
            booking=booking,
            start_at=start_at + timedelta(hours=2),
            end_at=end_at + timedelta(hours=2),
        )
    with pytest.raises(PermissionDenied):
        cancel_booking(actor=peer_user, booking=booking, reason="")


def test_override_requires_management_and_reason(
    member_user, manager_user, resource, future_window
):
    booking = create_default_booking(member_user, resource, future_window)

    with pytest.raises(PermissionDenied):
        cancel_booking(actor=member_user, booking=booking, reason="Owner override", override=True)
    with pytest.raises(DomainValidationError):
        cancel_booking(actor=manager_user, booking=booking, reason="", override=True)
