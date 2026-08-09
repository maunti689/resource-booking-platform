from django.conf import settings
from django.db import models
from django.db.models import F, Q

from apps.resources.models import Resource


class Booking(models.Model):
    class Status(models.TextChoices):
        CONFIRMED = "confirmed", "Подтверждено"
        CANCELLED = "cancelled", "Отменено"

    resource = models.ForeignKey(Resource, on_delete=models.PROTECT, related_name="bookings")
    owner = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.PROTECT, related_name="bookings"
    )
    start_at = models.DateTimeField()
    end_at = models.DateTimeField()
    purpose = models.CharField(max_length=240)
    status = models.CharField(max_length=16, choices=Status.choices, default=Status.CONFIRMED)
    cancelled_at = models.DateTimeField(null=True, blank=True)
    cancelled_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name="cancelled_bookings",
        null=True,
        blank=True,
    )
    cancel_reason = models.CharField(max_length=240, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        constraints = [
            models.CheckConstraint(
                condition=Q(end_at__gt=F("start_at")), name="ck_booking_time_order"
            )
        ]
        indexes = [
            models.Index(fields=["resource", "status", "start_at"]),
            models.Index(fields=["owner", "start_at"]),
        ]
        ordering = ["start_at"]


class BookingParticipant(models.Model):
    booking = models.ForeignKey(Booking, on_delete=models.CASCADE, related_name="participants")
    email = models.EmailField()

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=["booking", "email"], name="uq_booking_participant_email"
            )
        ]
        ordering = ["email"]


class ReminderDelivery(models.Model):
    class Kind(models.TextChoices):
        STARTING_SOON = "starting_soon", "Скоро начнётся"

    booking = models.ForeignKey(Booking, on_delete=models.CASCADE, related_name="reminders")
    kind = models.CharField(max_length=32, choices=Kind.choices)
    delivered_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(fields=["booking", "kind"], name="uq_booking_reminder_kind")
        ]
