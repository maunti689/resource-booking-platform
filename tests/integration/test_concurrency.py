from concurrent.futures import ThreadPoolExecutor
from threading import Barrier

import pytest
from django.contrib.auth import get_user_model
from django.db import connection, connections

from apps.bookings.models import Booking
from apps.bookings.services import create_booking
from apps.resources.models import Resource
from config.exceptions import ConflictError


@pytest.mark.postgresql
@pytest.mark.django_db(transaction=True)
def test_concurrent_overlapping_requests_create_only_one_booking(
    member_user, peer_user, resource, future_window
):
    if connection.vendor != "postgresql":
        pytest.skip("PostgreSQL row locking is required")

    barrier = Barrier(2)
    start_at, end_at = future_window

    def attempt(user_id):
        connections.close_all()
        actor = get_user_model().objects.get(pk=user_id)
        local_resource = Resource.objects.get(pk=resource.pk)
        barrier.wait()
        try:
            create_booking(
                actor=actor,
                resource=local_resource,
                start_at=start_at,
                end_at=end_at,
                purpose="Concurrent request",
                participant_emails=[],
            )
        except ConflictError:
            return "conflict"
        finally:
            connections.close_all()
        return "created"

    with ThreadPoolExecutor(max_workers=2) as executor:
        outcomes = list(executor.map(attempt, [member_user.id, peer_user.id]))

    assert sorted(outcomes) == ["conflict", "created"]
    assert Booking.objects.filter(resource=resource).count() == 1
