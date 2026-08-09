from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [("organizations", "0001_initial")]

    operations = [
        migrations.AddField(
            model_name="organization",
            name="max_booking_duration_minutes",
            field=models.PositiveIntegerField(default=480),
        ),
        migrations.AddConstraint(
            model_name="organization",
            constraint=models.CheckConstraint(
                condition=models.Q(
                    ("max_booking_duration_minutes__gte", 1),
                    ("max_booking_duration_minutes__lte", 1440),
                ),
                name="ck_organization_booking_duration",
            ),
        ),
    ]
