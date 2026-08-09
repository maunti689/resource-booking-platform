from datetime import datetime
from zoneinfo import ZoneInfo

from django.db import transaction
from django.db.models import Q
from django.utils import timezone
from rest_framework.exceptions import NotFound, PermissionDenied

from apps.audit.services import record_event
from apps.bookings.models import Booking, BookingParticipant
from apps.organizations.models import Organization
from apps.organizations.services import MANAGEMENT_ROLES, membership_for
from apps.resources.models import AvailabilityRule, BlackoutPeriod, Resource
from apps.resources.services import bump_availability_version
from config.exceptions import ConflictError, DomainValidationError


def _validate_time_range(resource: Resource, start_at: datetime, end_at: datetime) -> None:
    if end_at <= start_at:
        raise DomainValidationError("Бронирование должно закончиться после начала")
    duration_minutes = (end_at - start_at).total_seconds() / 60
    if duration_minutes > resource.organization.max_booking_duration_minutes:
        raise DomainValidationError("Длительность бронирования превышает лимит организации")
    if start_at <= timezone.now():
        raise DomainValidationError("Бронирование должно начинаться в будущем")
    local_start = timezone.localtime(start_at, timezone=ZoneInfo(resource.timezone))
    local_end = timezone.localtime(end_at, timezone=ZoneInfo(resource.timezone))
    if local_start.date() != local_end.date():
        raise DomainValidationError("Бронирование должно завершиться в тот же локальный день")
    rule = AvailabilityRule.objects.filter(resource=resource, weekday=local_start.weekday()).first()
    if not rule or local_start.time() < rule.start_time or local_end.time() > rule.end_time:
        raise DomainValidationError("Бронирование выходит за рабочие часы ресурса")


def _validate_no_conflicts(
    resource: Resource,
    start_at: datetime,
    end_at: datetime,
    exclude_booking_id: int | None = None,
) -> None:
    overlaps = Booking.objects.filter(
        resource=resource,
        status=Booking.Status.CONFIRMED,
        start_at__lt=end_at,
        end_at__gt=start_at,
    )
    if exclude_booking_id is not None:
        overlaps = overlaps.exclude(pk=exclude_booking_id)
    if overlaps.exists():
        raise ConflictError("Ресурс уже забронирован на этот интервал")
    if BlackoutPeriod.objects.filter(
        resource=resource, start_at__lt=end_at, end_at__gt=start_at
    ).exists():
        raise ConflictError("Ресурс недоступен в указанный период")


def _replace_participants(booking: Booking, participant_emails: list[str]) -> None:
    booking.participants.all().delete()
    BookingParticipant.objects.bulk_create(
        [
            BookingParticipant(booking=booking, email=email)
            for email in sorted(set(participant_emails))
        ]
    )


@transaction.atomic
def create_booking(
    *,
    actor,
    resource: Resource,
    start_at: datetime,
    end_at: datetime,
    purpose: str,
    participant_emails: list[str],
) -> Booking:
    membership_for(actor, resource.organization)
    locked_resource = Resource.objects.select_for_update().get(pk=resource.pk)
    if not locked_resource.is_active:
        raise DomainValidationError("Неактивный ресурс нельзя забронировать")
    _validate_time_range(locked_resource, start_at, end_at)
    _validate_no_conflicts(locked_resource, start_at, end_at)
    booking = Booking.objects.create(
        resource=locked_resource,
        owner=actor,
        start_at=start_at,
        end_at=end_at,
        purpose=purpose,
    )
    _replace_participants(booking, participant_emails)
    bump_availability_version(locked_resource)
    record_event(
        organization=locked_resource.organization,
        actor=actor,
        event_type="booking.created",
        target=booking,
        metadata={"resource_id": locked_resource.id},
    )
    return booking


def get_booking_for_member(*, actor, booking_id: int) -> Booking:
    try:
        booking = Booking.objects.select_related("resource__organization", "owner").get(
            pk=booking_id
        )
    except Booking.DoesNotExist as exc:
        raise NotFound("Бронирование не найдено") from exc
    membership_for(actor, booking.resource.organization)
    return booking


def _can_manage_booking(actor, booking: Booking) -> bool:
    membership = membership_for(actor, booking.resource.organization)
    return actor.id == booking.owner_id or membership.role in MANAGEMENT_ROLES


@transaction.atomic
def reschedule_booking(*, actor, booking: Booking, start_at: datetime, end_at: datetime) -> Booking:
    if not _can_manage_booking(actor, booking):
        raise PermissionDenied("Перенос доступен владельцу и руководству организации")
    locked_resource = Resource.objects.select_for_update().get(pk=booking.resource_id)
    locked_booking = Booking.objects.select_for_update().get(pk=booking.pk)
    if locked_booking.status != Booking.Status.CONFIRMED:
        raise ConflictError("Перенести можно только подтверждённое бронирование")
    _validate_time_range(locked_resource, start_at, end_at)
    _validate_no_conflicts(locked_resource, start_at, end_at, locked_booking.id)
    old_range = {
        "start_at": locked_booking.start_at.isoformat(),
        "end_at": locked_booking.end_at.isoformat(),
    }
    locked_booking.start_at = start_at
    locked_booking.end_at = end_at
    locked_booking.save(update_fields=["start_at", "end_at", "updated_at"])
    bump_availability_version(locked_resource)
    record_event(
        organization=locked_resource.organization,
        actor=actor,
        event_type="booking.rescheduled",
        target=locked_booking,
        metadata={"before": old_range},
    )
    return locked_booking


@transaction.atomic
def cancel_booking(*, actor, booking: Booking, reason: str, override: bool = False) -> Booking:
    membership = membership_for(actor, booking.resource.organization)
    if override:
        if membership.role not in MANAGEMENT_ROLES:
            raise PermissionDenied("Принудительная отмена доступна руководству организации")
        if not reason.strip():
            raise DomainValidationError("Для принудительной отмены требуется причина")
    elif actor.id != booking.owner_id and membership.role not in MANAGEMENT_ROLES:
        raise PermissionDenied("Отмена доступна владельцу и руководству организации")

    locked_resource = Resource.objects.select_for_update().get(pk=booking.resource_id)
    locked_booking = Booking.objects.select_for_update().get(pk=booking.pk)
    if locked_booking.status != Booking.Status.CONFIRMED:
        raise ConflictError("Бронирование уже отменено")
    locked_booking.status = Booking.Status.CANCELLED
    locked_booking.cancelled_at = timezone.now()
    locked_booking.cancelled_by = actor
    locked_booking.cancel_reason = reason
    locked_booking.save(
        update_fields=[
            "status",
            "cancelled_at",
            "cancelled_by",
            "cancel_reason",
            "updated_at",
        ]
    )
    bump_availability_version(locked_resource)
    record_event(
        organization=locked_resource.organization,
        actor=actor,
        event_type="booking.override_cancelled" if override else "booking.cancelled",
        target=locked_booking,
        metadata={"reason": reason},
    )
    return locked_booking


def list_bookings(
    *,
    actor,
    organization: Organization,
    resource_id: int | None = None,
    start_at: datetime | None = None,
    end_at: datetime | None = None,
    status: str | None = None,
):
    membership_for(actor, organization)
    bookings = Booking.objects.filter(resource__organization=organization).select_related(
        "resource", "owner"
    )
    if resource_id is not None:
        bookings = bookings.filter(resource_id=resource_id)
    if start_at is not None:
        bookings = bookings.filter(end_at__gt=start_at)
    if end_at is not None:
        bookings = bookings.filter(start_at__lt=end_at)
    if status is not None:
        bookings = bookings.filter(status=status)
    return bookings.prefetch_related("participants")


def my_schedule(*, actor, start_at: datetime | None = None, end_at: datetime | None = None):
    query = Q(owner=actor) | Q(participants__email__iexact=actor.email)
    bookings = Booking.objects.filter(query).select_related("resource", "owner").distinct()
    if start_at is not None:
        bookings = bookings.filter(end_at__gt=start_at)
    if end_at is not None:
        bookings = bookings.filter(start_at__lt=end_at)
    return bookings.prefetch_related("participants")
