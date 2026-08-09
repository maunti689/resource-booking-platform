from django.urls import path

from apps.bookings.views import (
    BookingCancelView,
    BookingDetailView,
    BookingListCreateView,
    BookingOverrideCancelView,
    BookingRescheduleView,
    MyScheduleView,
)

urlpatterns = [
    path("bookings", BookingListCreateView.as_view(), name="bookings"),
    path("bookings/<int:booking_id>", BookingDetailView.as_view(), name="booking-detail"),
    path(
        "bookings/<int:booking_id>/reschedule",
        BookingRescheduleView.as_view(),
        name="booking-reschedule",
    ),
    path(
        "bookings/<int:booking_id>/cancel",
        BookingCancelView.as_view(),
        name="booking-cancel",
    ),
    path(
        "bookings/<int:booking_id>/override-cancel",
        BookingOverrideCancelView.as_view(),
        name="booking-override-cancel",
    ),
    path("me/schedule", MyScheduleView.as_view(), name="my-schedule"),
]
