from django.conf import settings
from django.db import models


class Organization(models.Model):
    name = models.CharField(max_length=160)
    slug = models.SlugField(max_length=160, unique=True)
    max_booking_duration_minutes = models.PositiveIntegerField(default=480)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        constraints = [
            models.CheckConstraint(
                condition=models.Q(
                    max_booking_duration_minutes__gte=1,
                    max_booking_duration_minutes__lte=1440,
                ),
                name="ck_organization_booking_duration",
            )
        ]
        ordering = ["name"]

    def __str__(self) -> str:
        return self.name


class Membership(models.Model):
    class Role(models.TextChoices):
        ADMIN = "admin", "Администратор"
        MANAGER = "manager", "Менеджер"
        MEMBER = "member", "Участник"

    organization = models.ForeignKey(
        Organization, on_delete=models.CASCADE, related_name="memberships"
    )
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="organization_memberships"
    )
    role = models.CharField(max_length=16, choices=Role.choices, default=Role.MEMBER)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=["organization", "user"], name="uq_membership_organization_user"
            )
        ]
        indexes = [models.Index(fields=["user", "organization"])]

    def __str__(self) -> str:
        return f"{self.organization_id}:{self.user_id}:{self.role}"
