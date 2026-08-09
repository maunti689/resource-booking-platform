from django.conf import settings
from django.contrib.auth import get_user_model
from django.db import transaction
from django.shortcuts import get_object_or_404
from rest_framework.exceptions import NotFound, PermissionDenied

from apps.audit.services import record_event
from apps.organizations.models import Membership, Organization
from config.exceptions import ConflictError

MANAGEMENT_ROLES = {Membership.Role.ADMIN, Membership.Role.MANAGER}


def membership_for(user, organization: Organization) -> Membership:
    try:
        return Membership.objects.get(user=user, organization=organization)
    except Membership.DoesNotExist as exc:
        raise NotFound("Организация не найдена") from exc


def require_role(user, organization: Organization, roles: set[str]) -> Membership:
    membership = membership_for(user, organization)
    if membership.role not in roles:
        raise PermissionDenied("Роль в организации не позволяет выполнить эту операцию")
    return membership


@transaction.atomic
def create_organization(
    *,
    actor,
    name: str,
    slug: str,
    max_booking_duration_minutes: int | None = None,
) -> Organization:
    organization = Organization.objects.create(
        name=name,
        slug=slug,
        max_booking_duration_minutes=(
            settings.BOOKING_DEFAULT_MAX_DURATION_MINUTES
            if max_booking_duration_minutes is None
            else max_booking_duration_minutes
        ),
    )
    Membership.objects.create(organization=organization, user=actor, role=Membership.Role.ADMIN)
    record_event(
        organization=organization,
        actor=actor,
        event_type="organization.created",
        target=organization,
    )
    return organization


@transaction.atomic
def update_organization(*, actor, organization: Organization, changes: dict) -> Organization:
    require_role(actor, organization, {Membership.Role.ADMIN})
    locked = Organization.objects.select_for_update().get(pk=organization.pk)
    changed_fields = []
    for field, value in changes.items():
        if getattr(locked, field) != value:
            setattr(locked, field, value)
            changed_fields.append(field)
    if changed_fields:
        locked.save(update_fields=changed_fields)
        record_event(
            organization=locked,
            actor=actor,
            event_type="organization.updated",
            target=locked,
            metadata={"fields": changed_fields},
        )
    return locked


@transaction.atomic
def add_member(*, actor, organization: Organization, username: str, role: str) -> Membership:
    require_role(actor, organization, {Membership.Role.ADMIN})
    user_model = get_user_model()
    user = get_object_or_404(user_model, username=username)
    membership, created = Membership.objects.get_or_create(
        organization=organization,
        user=user,
        defaults={"role": role},
    )
    if not created:
        raise ConflictError("Пользователь уже состоит в этой организации")
    record_event(
        organization=organization,
        actor=actor,
        event_type="membership.added",
        target=membership,
        metadata={"user_id": user.id, "role": role},
    )
    return membership


@transaction.atomic
def update_member_role(
    *, actor, organization: Organization, membership: Membership, role: str
) -> Membership:
    actor_membership = require_role(actor, organization, {Membership.Role.ADMIN})
    if membership.organization_id != organization.id:
        raise NotFound("Участник организации не найден")
    if membership.id == actor_membership.id and role != Membership.Role.ADMIN:
        raise PermissionDenied("Администратор не может понизить собственную роль")
    previous_role = membership.role
    membership.role = role
    membership.save(update_fields=["role"])
    record_event(
        organization=organization,
        actor=actor,
        event_type="membership.role_updated",
        target=membership,
        metadata={"previous_role": previous_role, "role": role},
    )
    return membership


@transaction.atomic
def remove_member(*, actor, organization: Organization, membership: Membership) -> None:
    actor_membership = require_role(actor, organization, {Membership.Role.ADMIN})
    if membership.organization_id != organization.id:
        raise NotFound("Участник организации не найден")
    if membership.id == actor_membership.id:
        raise PermissionDenied("Администратор не может удалить себя из организации")
    record_event(
        organization=organization,
        actor=actor,
        event_type="membership.removed",
        target=membership,
        metadata={"user_id": membership.user_id, "role": membership.role},
    )
    membership.delete()
