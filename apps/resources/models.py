from django.conf import settings
from django.db import models
from django.db.models import F, Q

from apps.organizations.models import Organization


class Resource(models.Model):
    class Type(models.TextChoices):
        ROOM = "room", "Помещение"
        EQUIPMENT = "equipment", "Оборудование"
        OTHER = "other", "Другое"

    organization = models.ForeignKey(
        Organization, on_delete=models.CASCADE, related_name="resources"
    )
    name = models.CharField(max_length=160)
    resource_type = models.CharField(max_length=20, choices=Type.choices, default=Type.ROOM)
    capacity = models.PositiveIntegerField(default=1)
    timezone = models.CharField(max_length=64, default="UTC")
    is_active = models.BooleanField(default=True)
    availability_version = models.PositiveBigIntegerField(default=1)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=["organization", "name"], name="uq_resource_organization_name"
            ),
            models.CheckConstraint(
                condition=Q(capacity__gt=0), name="ck_resource_capacity_positive"
            ),
        ]
        indexes = [models.Index(fields=["organization", "is_active", "capacity"])]
        ordering = ["name"]

    def __str__(self) -> str:
        return self.name


class AvailabilityRule(models.Model):
    resource = models.ForeignKey(
        Resource, on_delete=models.CASCADE, related_name="availability_rules"
    )
    weekday = models.PositiveSmallIntegerField()
    start_time = models.TimeField()
    end_time = models.TimeField()

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=["resource", "weekday"], name="uq_availability_rule_resource_weekday"
            ),
            models.CheckConstraint(
                condition=Q(weekday__gte=0, weekday__lte=6), name="ck_availability_weekday"
            ),
            models.CheckConstraint(
                condition=Q(end_time__gt=F("start_time")), name="ck_availability_time_order"
            ),
        ]
        ordering = ["weekday"]


class BlackoutPeriod(models.Model):
    resource = models.ForeignKey(Resource, on_delete=models.CASCADE, related_name="blackouts")
    start_at = models.DateTimeField()
    end_at = models.DateTimeField()
    reason = models.CharField(max_length=240)
    created_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        constraints = [
            models.CheckConstraint(
                condition=Q(end_at__gt=F("start_at")), name="ck_blackout_time_order"
            )
        ]
        indexes = [models.Index(fields=["resource", "start_at", "end_at"])]
        ordering = ["start_at"]
