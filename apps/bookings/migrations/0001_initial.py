import django.db.models.deletion
from django.conf import settings
from django.db import migrations, models


class Migration(migrations.Migration):
    initial = True

    dependencies = [
        ("resources", "0001_initial"),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.CreateModel(
            name="Booking",
            fields=[
                (
                    "id",
                    models.BigAutoField(
                        auto_created=True,
                        primary_key=True,
                        serialize=False,
                        verbose_name="ID",
                    ),
                ),
                ("start_at", models.DateTimeField()),
                ("end_at", models.DateTimeField()),
                ("purpose", models.CharField(max_length=240)),
                (
                    "status",
                    models.CharField(
                        choices=[
                            ("confirmed", "Подтверждено"),
                            ("cancelled", "Отменено"),
                        ],
                        default="confirmed",
                        max_length=16,
                    ),
                ),
                ("cancelled_at", models.DateTimeField(blank=True, null=True)),
                ("cancel_reason", models.CharField(blank=True, max_length=240)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                (
                    "cancelled_by",
                    models.ForeignKey(
                        blank=True,
                        null=True,
                        on_delete=django.db.models.deletion.PROTECT,
                        related_name="cancelled_bookings",
                        to=settings.AUTH_USER_MODEL,
                    ),
                ),
                (
                    "owner",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.PROTECT,
                        related_name="bookings",
                        to=settings.AUTH_USER_MODEL,
                    ),
                ),
                (
                    "resource",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.PROTECT,
                        related_name="bookings",
                        to="resources.resource",
                    ),
                ),
            ],
            options={"ordering": ["start_at"]},
        ),
        migrations.CreateModel(
            name="BookingParticipant",
            fields=[
                (
                    "id",
                    models.BigAutoField(
                        auto_created=True,
                        primary_key=True,
                        serialize=False,
                        verbose_name="ID",
                    ),
                ),
                ("email", models.EmailField(max_length=254)),
                (
                    "booking",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="participants",
                        to="bookings.booking",
                    ),
                ),
            ],
            options={"ordering": ["email"]},
        ),
        migrations.CreateModel(
            name="ReminderDelivery",
            fields=[
                (
                    "id",
                    models.BigAutoField(
                        auto_created=True,
                        primary_key=True,
                        serialize=False,
                        verbose_name="ID",
                    ),
                ),
                (
                    "kind",
                    models.CharField(choices=[("starting_soon", "Скоро начнётся")], max_length=32),
                ),
                ("delivered_at", models.DateTimeField(auto_now_add=True)),
                (
                    "booking",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="reminders",
                        to="bookings.booking",
                    ),
                ),
            ],
        ),
        migrations.AddIndex(
            model_name="booking",
            index=models.Index(
                fields=["resource", "status", "start_at"],
                name="bookings_bo_resourc_83923b_idx",
            ),
        ),
        migrations.AddIndex(
            model_name="booking",
            index=models.Index(
                fields=["owner", "start_at"],
                name="bookings_bo_owner_i_d15648_idx",
            ),
        ),
        migrations.AddConstraint(
            model_name="booking",
            constraint=models.CheckConstraint(
                condition=models.Q(("end_at__gt", models.F("start_at"))),
                name="ck_booking_time_order",
            ),
        ),
        migrations.AddConstraint(
            model_name="bookingparticipant",
            constraint=models.UniqueConstraint(
                fields=("booking", "email"), name="uq_booking_participant_email"
            ),
        ),
        migrations.AddConstraint(
            model_name="reminderdelivery",
            constraint=models.UniqueConstraint(
                fields=("booking", "kind"), name="uq_booking_reminder_kind"
            ),
        ),
    ]
