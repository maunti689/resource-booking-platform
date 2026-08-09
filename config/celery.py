import os

from celery import Celery
from celery.schedules import crontab

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings")

app = Celery("resource_booking")
app.config_from_object("django.conf:settings", namespace="CELERY")
app.autodiscover_tasks()
app.conf.beat_schedule = {
    "send-upcoming-booking-reminders": {
        "task": "apps.bookings.tasks.send_upcoming_booking_reminders",
        "schedule": crontab(minute="*/5"),
    }
}
