from datetime import datetime, time, timedelta, timezone

import pytest
from django.core.cache import cache
from rest_framework.test import APIClient


@pytest.fixture(autouse=True)
def clear_test_cache():
    cache.clear()
    yield
    cache.clear()


@pytest.fixture
def user_model():
    from django.contrib.auth import get_user_model

    return get_user_model()


@pytest.fixture
def admin_user(db, user_model):
    return user_model.objects.create_user(
        username="admin", email="admin@example.com", password="password"
    )


@pytest.fixture
def manager_user(db, user_model):
    return user_model.objects.create_user(
        username="manager", email="manager@example.com", password="password"
    )


@pytest.fixture
def member_user(db, user_model):
    return user_model.objects.create_user(
        username="member", email="member@example.com", password="password"
    )


@pytest.fixture
def peer_user(db, user_model):
    return user_model.objects.create_user(
        username="peer", email="peer@example.com", password="password"
    )


@pytest.fixture
def outsider_user(db, user_model):
    return user_model.objects.create_user(
        username="outsider", email="outsider@example.com", password="password"
    )


@pytest.fixture
def organization(db, admin_user, manager_user, member_user, peer_user):
    from apps.organizations.models import Membership, Organization

    organization = Organization.objects.create(name="North Office", slug="north-office")
    Membership.objects.create(
        organization=organization, user=admin_user, role=Membership.Role.ADMIN
    )
    Membership.objects.create(
        organization=organization, user=manager_user, role=Membership.Role.MANAGER
    )
    Membership.objects.create(
        organization=organization, user=member_user, role=Membership.Role.MEMBER
    )
    Membership.objects.create(
        organization=organization, user=peer_user, role=Membership.Role.MEMBER
    )
    return organization


@pytest.fixture
def second_organization(db, outsider_user):
    from apps.organizations.models import Membership, Organization

    organization = Organization.objects.create(name="South Office", slug="south-office")
    Membership.objects.create(
        organization=organization, user=outsider_user, role=Membership.Role.ADMIN
    )
    return organization


@pytest.fixture
def resource(organization):
    from apps.resources.models import AvailabilityRule, Resource

    resource = Resource.objects.create(
        organization=organization,
        name="Meeting Room A",
        capacity=8,
        timezone="UTC",
    )
    AvailabilityRule.objects.bulk_create(
        [
            AvailabilityRule(
                resource=resource,
                weekday=weekday,
                start_time=time(9, 0),
                end_time=time(18, 0),
            )
            for weekday in range(7)
        ]
    )
    return resource


@pytest.fixture
def second_resource(second_organization):
    from apps.resources.models import Resource

    return Resource.objects.create(
        organization=second_organization,
        name="Private Room",
        capacity=4,
        timezone="UTC",
    )


@pytest.fixture
def future_window():
    target_date = (datetime.now(timezone.utc) + timedelta(days=2)).date()
    start_at = datetime.combine(target_date, time(10, 0), tzinfo=timezone.utc)
    return start_at, start_at + timedelta(hours=1)


@pytest.fixture
def api_client():
    return APIClient()


@pytest.fixture
def client_for():
    def create_client(user):
        client = APIClient()
        client.force_authenticate(user=user)
        return client

    return create_client
