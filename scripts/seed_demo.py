import os
from datetime import datetime, time, timedelta, timezone
from zoneinfo import ZoneInfo


def next_weekday_start() -> datetime:
    local_timezone = ZoneInfo("Europe/Moscow")
    target = datetime.now(local_timezone).date() + timedelta(days=1)
    while target.weekday() >= 5:
        target += timedelta(days=1)
    local_start = datetime.combine(target, time(12, 0), tzinfo=local_timezone)
    return local_start.astimezone(timezone.utc)


def main() -> None:
    os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings")

    import django

    django.setup()

    from django.contrib.auth import get_user_model

    from apps.bookings.models import Booking, BookingParticipant
    from apps.organizations.models import Membership, Organization
    from apps.resources.models import AvailabilityRule, Resource

    user_model = get_user_model()
    admin, _ = user_model.objects.get_or_create(
        username="demo_admin", defaults={"email": "admin@example.com"}
    )
    admin.email = "admin@example.com"
    admin.set_password("demo-pass")
    admin.save(update_fields=["email", "password"])

    member, _ = user_model.objects.get_or_create(
        username="demo_member", defaults={"email": "member@example.com"}
    )
    member.email = "member@example.com"
    member.set_password("demo-pass")
    member.save(update_fields=["email", "password"])

    manager, _ = user_model.objects.get_or_create(
        username="demo_manager", defaults={"email": "manager@example.com"}
    )
    manager.email = "manager@example.com"
    manager.set_password("demo-pass")
    manager.save(update_fields=["email", "password"])

    organization, _ = Organization.objects.get_or_create(
        slug="north-office",
        defaults={
            "name": "Северный офис",
            "max_booking_duration_minutes": 120,
        },
    )
    organization.name = "Северный офис"
    organization.max_booking_duration_minutes = 120
    organization.save(update_fields=["name", "max_booking_duration_minutes"])
    Membership.objects.update_or_create(
        organization=organization,
        user=admin,
        defaults={"role": Membership.Role.ADMIN},
    )
    Membership.objects.update_or_create(
        organization=organization,
        user=manager,
        defaults={"role": Membership.Role.MANAGER},
    )
    Membership.objects.update_or_create(
        organization=organization,
        user=member,
        defaults={"role": Membership.Role.MEMBER},
    )

    resource, _ = Resource.objects.get_or_create(
        organization=organization,
        name="Переговорная А",
        defaults={
            "resource_type": Resource.Type.ROOM,
            "capacity": 8,
            "timezone": "Europe/Moscow",
        },
    )
    for weekday in range(5):
        AvailabilityRule.objects.update_or_create(
            resource=resource,
            weekday=weekday,
            defaults={"start_time": time(9, 0), "end_time": time(18, 0)},
        )

    start_at = next_weekday_start()
    booking, _ = Booking.objects.get_or_create(
        resource=resource,
        owner=admin,
        start_at=start_at,
        defaults={
            "end_at": start_at + timedelta(hours=1),
            "purpose": "Еженедельное планирование",
        },
    )
    BookingParticipant.objects.get_or_create(booking=booking, email=member.email)

    print("Демонстрационные данные готовы")
    print("Администратор: demo_admin / demo-pass")
    print("Менеджер: demo_manager / demo-pass")
    print("Участник: demo_member / demo-pass")
    print(f"ID организации: {organization.id}; ID ресурса: {resource.id}")


if __name__ == "__main__":
    main()
