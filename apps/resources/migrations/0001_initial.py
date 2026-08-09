import django.db.models.deletion
from django.conf import settings
from django.db import migrations, models


class Migration(migrations.Migration):
    initial = True

    dependencies = [
        ("organizations", "0001_initial"),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.CreateModel(
            name="Resource",
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
                ("name", models.CharField(max_length=160)),
                (
                    "resource_type",
                    models.CharField(
                        choices=[
                            ("room", "Помещение"),
                            ("equipment", "Оборудование"),
                            ("other", "Другое"),
                        ],
                        default="room",
                        max_length=20,
                    ),
                ),
                ("capacity", models.PositiveIntegerField(default=1)),
                ("timezone", models.CharField(default="UTC", max_length=64)),
                ("is_active", models.BooleanField(default=True)),
                ("availability_version", models.PositiveBigIntegerField(default=1)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                (
                    "organization",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="resources",
                        to="organizations.organization",
                    ),
                ),
            ],
            options={"ordering": ["name"]},
        ),
        migrations.CreateModel(
            name="BlackoutPeriod",
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
                ("reason", models.CharField(max_length=240)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                (
                    "created_by",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.PROTECT,
                        to=settings.AUTH_USER_MODEL,
                    ),
                ),
                (
                    "resource",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="blackouts",
                        to="resources.resource",
                    ),
                ),
            ],
            options={"ordering": ["start_at"]},
        ),
        migrations.CreateModel(
            name="AvailabilityRule",
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
                ("weekday", models.PositiveSmallIntegerField()),
                ("start_time", models.TimeField()),
                ("end_time", models.TimeField()),
                (
                    "resource",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="availability_rules",
                        to="resources.resource",
                    ),
                ),
            ],
            options={"ordering": ["weekday"]},
        ),
        migrations.AddIndex(
            model_name="resource",
            index=models.Index(
                fields=["organization", "is_active", "capacity"],
                name="resources_r_organiz_949d96_idx",
            ),
        ),
        migrations.AddConstraint(
            model_name="resource",
            constraint=models.UniqueConstraint(
                fields=("organization", "name"),
                name="uq_resource_organization_name",
            ),
        ),
        migrations.AddConstraint(
            model_name="resource",
            constraint=models.CheckConstraint(
                condition=models.Q(("capacity__gt", 0)),
                name="ck_resource_capacity_positive",
            ),
        ),
        migrations.AddIndex(
            model_name="blackoutperiod",
            index=models.Index(
                fields=["resource", "start_at", "end_at"],
                name="resources_b_resourc_ca57cc_idx",
            ),
        ),
        migrations.AddConstraint(
            model_name="blackoutperiod",
            constraint=models.CheckConstraint(
                condition=models.Q(("end_at__gt", models.F("start_at"))),
                name="ck_blackout_time_order",
            ),
        ),
        migrations.AddConstraint(
            model_name="availabilityrule",
            constraint=models.UniqueConstraint(
                fields=("resource", "weekday"),
                name="uq_availability_rule_resource_weekday",
            ),
        ),
        migrations.AddConstraint(
            model_name="availabilityrule",
            constraint=models.CheckConstraint(
                condition=models.Q(("weekday__gte", 0), ("weekday__lte", 6)),
                name="ck_availability_weekday",
            ),
        ),
        migrations.AddConstraint(
            model_name="availabilityrule",
            constraint=models.CheckConstraint(
                condition=models.Q(("end_time__gt", models.F("start_time"))),
                name="ck_availability_time_order",
            ),
        ),
    ]
