from datetime import date, datetime, time, timedelta, timezone
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from django.conf import settings
from django.core.cache import cache
from django.db import transaction
from django.db.models import F, Prefetch, prefetch_related_objects
from django.utils import timezone as django_timezone
from rest_framework.exceptions import NotFound

from apps.audit.services import record_event
from apps.bookings.models import Booking
from apps.organizations.models import Organization
from apps.organizations.services import MANAGEMENT_ROLES, membership_for, require_role
from apps.resources.models import AvailabilityRule, BlackoutPeriod, Resource
from config.exceptions import DomainValidationError


def validate_timezone(timezone_name: str) -> None:
    try:
        ZoneInfo(timezone_name)
    except ZoneInfoNotFoundError as exc:
        raise DomainValidationError("Неизвестная временная зона IANA") from exc


def bump_availability_version(resource: Resource) -> None:
    Resource.objects.filter(pk=resource.pk).update(
        availability_version=F("availability_version") + 1
    )
    resource.refresh_from_db(fields=["availability_version"])


@transaction.atomic
def create_resource(
    *,
    actor,
    organization: Organization,
    name: str,
    resource_type: str,
    capacity: int,
    timezone_name: str,
) -> Resource:
    require_role(actor, organization, MANAGEMENT_ROLES)
    validate_timezone(timezone_name)
    resource = Resource.objects.create(
        organization=organization,
        name=name,
        resource_type=resource_type,
        capacity=capacity,
        timezone=timezone_name,
    )
    record_event(
        organization=organization,
        actor=actor,
        event_type="resource.created",
        target=resource,
    )
    return resource


@transaction.atomic
def update_resource(
    *, actor, organization: Organization, resource: Resource, changes: dict
) -> Resource:
    require_role(actor, organization, MANAGEMENT_ROLES)
    try:
        locked = Resource.objects.select_for_update().get(pk=resource.pk, organization=organization)
    except Resource.DoesNotExist as exc:
        raise NotFound("Ресурс не найден") from exc
    if "timezone" in changes:
        validate_timezone(changes["timezone"])
    changed_fields = []
    for field, value in changes.items():
        if getattr(locked, field) != value:
            setattr(locked, field, value)
            changed_fields.append(field)
    if changed_fields:
        locked.availability_version += 1
        changed_fields.extend(["availability_version", "updated_at"])
        locked.save(update_fields=changed_fields)
        record_event(
            organization=organization,
            actor=actor,
            event_type="resource.updated",
            target=locked,
            metadata={"fields": changed_fields},
        )
    return locked


@transaction.atomic
def deactivate_resource(*, actor, organization: Organization, resource: Resource) -> None:
    require_role(actor, organization, MANAGEMENT_ROLES)
    try:
        locked = Resource.objects.select_for_update().get(pk=resource.pk, organization=organization)
    except Resource.DoesNotExist as exc:
        raise NotFound("Ресурс не найден") from exc
    if not locked.is_active:
        return
    locked.is_active = False
    locked.availability_version += 1
    locked.save(update_fields=["is_active", "availability_version", "updated_at"])
    record_event(
        organization=organization,
        actor=actor,
        event_type="resource.archived",
        target=locked,
    )


@transaction.atomic
def upsert_availability_rule(
    *,
    actor,
    organization: Organization,
    resource: Resource,
    weekday: int,
    start_time: time,
    end_time: time,
) -> AvailabilityRule:
    require_role(actor, organization, MANAGEMENT_ROLES)
    try:
        locked = Resource.objects.select_for_update().get(pk=resource.pk, organization=organization)
    except Resource.DoesNotExist as exc:
        raise NotFound("Ресурс не найден") from exc
    rule, _ = AvailabilityRule.objects.update_or_create(
        resource=locked,
        weekday=weekday,
        defaults={"start_time": start_time, "end_time": end_time},
    )
    bump_availability_version(locked)
    record_event(
        organization=organization,
        actor=actor,
        event_type="availability_rule.updated",
        target=rule,
    )
    return rule


@transaction.atomic
def create_blackout(
    *,
    actor,
    organization: Organization,
    resource: Resource,
    start_at: datetime,
    end_at: datetime,
    reason: str,
) -> BlackoutPeriod:
    require_role(actor, organization, MANAGEMENT_ROLES)
    if end_at <= start_at:
        raise DomainValidationError("Период недоступности должен закончиться после начала")
    try:
        locked = Resource.objects.select_for_update().get(pk=resource.pk, organization=organization)
    except Resource.DoesNotExist as exc:
        raise NotFound("Ресурс не найден") from exc
    blackout = BlackoutPeriod.objects.create(
        resource=locked,
        start_at=start_at,
        end_at=end_at,
        reason=reason,
        created_by=actor,
    )
    bump_availability_version(locked)
    record_event(
        organization=organization,
        actor=actor,
        event_type="blackout.created",
        target=blackout,
        metadata={"resource_id": locked.id},
    )
    return blackout


def _overlaps(
    start_at: datetime,
    end_at: datetime,
    busy_start: datetime,
    busy_end: datetime,
) -> bool:
    return start_at < busy_end and end_at > busy_start


def _availability_cache_key(resource: Resource, target_date: date, duration_minutes: int) -> str:
    return (
        f"availability:{resource.id}:{resource.availability_version}:"
        f"{target_date.isoformat()}:{duration_minutes}"
    )


def _calculate_resource_slots(
    resource: Resource, target_date: date, duration_minutes: int
) -> list[dict]:
    local_timezone = ZoneInfo(resource.timezone)
    rules = resource.target_date_rules
    if not rules:
        return []
    rule = rules[0]

    local_start = datetime.combine(target_date, rule.start_time, tzinfo=local_timezone)
    local_end = datetime.combine(target_date, rule.end_time, tzinfo=local_timezone)
    window_start = local_start.astimezone(timezone.utc)
    window_end = local_end.astimezone(timezone.utc)
    busy = [(booking.start_at, booking.end_at) for booking in resource.availability_bookings]
    busy.extend(
        (blackout.start_at, blackout.end_at) for blackout in resource.availability_blackouts
    )

    slots = []
    duration = timedelta(minutes=duration_minutes)
    step = timedelta(minutes=settings.AVAILABILITY_SLOT_STEP_MINUTES)
    cursor = window_start
    now = django_timezone.now()
    while cursor + duration <= window_end:
        slot_end = cursor + duration
        if cursor >= now and not any(
            _overlaps(cursor, slot_end, busy_start, busy_end) for busy_start, busy_end in busy
        ):
            slots.append({"start_at": cursor.isoformat(), "end_at": slot_end.isoformat()})
        cursor += step

    return slots


def find_available_slots(
    *,
    actor,
    organization: Organization,
    target_date: date,
    duration_minutes: int,
    capacity: int | None = None,
    resource_id: int | None = None,
) -> list[dict]:
    membership_for(actor, organization)
    if duration_minutes <= 0 or duration_minutes > organization.max_booking_duration_minutes:
        raise DomainValidationError("Запрошенная длительность выходит за допустимые пределы")
    resources = Resource.objects.filter(organization=organization, is_active=True)
    if capacity is not None:
        resources = resources.filter(capacity__gte=capacity)
    if resource_id is not None:
        resources = resources.filter(pk=resource_id)
    resources = list(resources)
    cache_keys = {
        resource.id: _availability_cache_key(resource, target_date, duration_minutes)
        for resource in resources
    }
    cached_slots = cache.get_many(cache_keys.values())
    missing_resources = [
        resource for resource in resources if cache_keys[resource.id] not in cached_slots
    ]
    if missing_resources:
        query_start = datetime.combine(
            target_date - timedelta(days=1), time.min, tzinfo=timezone.utc
        )
        query_end = datetime.combine(target_date + timedelta(days=2), time.min, tzinfo=timezone.utc)
        prefetch_related_objects(
            missing_resources,
            Prefetch(
                "availability_rules",
                queryset=AvailabilityRule.objects.filter(weekday=target_date.weekday()),
                to_attr="target_date_rules",
            ),
            Prefetch(
                "bookings",
                queryset=Booking.objects.filter(
                    status=Booking.Status.CONFIRMED,
                    start_at__lt=query_end,
                    end_at__gt=query_start,
                ),
                to_attr="availability_bookings",
            ),
            Prefetch(
                "blackouts",
                queryset=BlackoutPeriod.objects.filter(
                    start_at__lt=query_end,
                    end_at__gt=query_start,
                ),
                to_attr="availability_blackouts",
            ),
        )

    cache_updates = {}
    slots_by_resource_id = {}
    for resource in resources:
        cache_key = cache_keys[resource.id]
        if cache_key in cached_slots:
            slots = cached_slots[cache_key]
        else:
            slots = _calculate_resource_slots(resource, target_date, duration_minutes)
            cache_updates[cache_key] = slots
        slots_by_resource_id[resource.id] = slots
    if cache_updates:
        cache.set_many(cache_updates, timeout=settings.AVAILABILITY_CACHE_TTL_SECONDS)

    result = []
    for resource in resources:
        slots = slots_by_resource_id[resource.id]
        if slots:
            result.append(
                {
                    "resource_id": resource.id,
                    "resource_name": resource.name,
                    "timezone": resource.timezone,
                    "slots": slots,
                }
            )
    return result


def get_resource_for_member(*, actor, organization: Organization, resource_id: int) -> Resource:
    membership_for(actor, organization)
    try:
        return Resource.objects.get(pk=resource_id, organization=organization)
    except Resource.DoesNotExist as exc:
        raise NotFound("Ресурс не найден") from exc
