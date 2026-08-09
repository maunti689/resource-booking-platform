import logging
from datetime import timedelta

from celery import shared_task
from django.conf import settings
from django.db import IntegrityError, OperationalError, transaction
from django.utils import timezone

from apps.bookings.models import Booking, ReminderDelivery

logger = logging.getLogger(__name__)


@shared_task(
    name="apps.bookings.tasks.send_upcoming_booking_reminders",
    autoretry_for=(OperationalError,),
    retry_backoff=True,
    retry_backoff_max=300,
    retry_jitter=True,
    max_retries=5,
)
def send_upcoming_booking_reminders() -> dict[str, int]:
    now = timezone.now()
    window_end = now + timedelta(minutes=settings.BOOKING_REMINDER_LEAD_MINUTES)
    bookings = Booking.objects.filter(
        status=Booking.Status.CONFIRMED,
        start_at__gt=now,
        start_at__lte=window_end,
    ).select_related("owner", "resource")
    delivered = 0
    for booking in bookings.iterator():
        try:
            with transaction.atomic():
                ReminderDelivery.objects.create(
                    booking=booking, kind=ReminderDelivery.Kind.STARTING_SOON
                )
        except IntegrityError:
            continue
        logger.info(
            "Напоминание о бронировании доставлено",
            extra={
                "booking_id": booking.id,
                "resource_id": booking.resource_id,
                "user_id": booking.owner_id,
            },
        )
        delivered += 1
    return {"delivered": delivered}
