from django.shortcuts import get_object_or_404
from drf_spectacular.utils import extend_schema
from rest_framework import status
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.bookings.serializers import (
    BookingCreateSerializer,
    BookingFilterSerializer,
    BookingSerializer,
    CancelSerializer,
    OverrideCancelSerializer,
    RescheduleSerializer,
    ScheduleFilterSerializer,
)
from apps.bookings.services import (
    cancel_booking,
    create_booking,
    get_booking_for_member,
    list_bookings,
    my_schedule,
    reschedule_booking,
)
from apps.organizations.models import Organization


class BookingListCreateView(APIView):
    @extend_schema(
        operation_id="bookings_list",
        summary="Получить бронирования",
        tags=["Бронирования"],
        parameters=[BookingFilterSerializer],
        responses=BookingSerializer(many=True),
    )
    def get(self, request):
        serializer = BookingFilterSerializer(data=request.query_params)
        serializer.is_valid(raise_exception=True)
        organization = get_object_or_404(
            Organization, pk=serializer.validated_data.pop("organization_id")
        )
        bookings = list_bookings(
            actor=request.user, organization=organization, **serializer.validated_data
        )
        return Response(BookingSerializer(bookings, many=True).data)

    @extend_schema(
        operation_id="bookings_create",
        summary="Создать бронирование",
        tags=["Бронирования"],
        request=BookingCreateSerializer,
        responses={201: BookingSerializer},
    )
    def post(self, request):
        serializer = BookingCreateSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        booking = create_booking(
            actor=request.user,
            resource=serializer.validated_data["resource"],
            start_at=serializer.validated_data["start_at"],
            end_at=serializer.validated_data["end_at"],
            purpose=serializer.validated_data["purpose"],
            participant_emails=serializer.validated_data.get("participants", []),
        )
        return Response(BookingSerializer(booking).data, status=status.HTTP_201_CREATED)


class BookingDetailView(APIView):
    @extend_schema(
        operation_id="bookings_retrieve",
        summary="Получить бронирование",
        tags=["Бронирования"],
        responses=BookingSerializer,
    )
    def get(self, request, booking_id):
        booking = get_booking_for_member(actor=request.user, booking_id=booking_id)
        return Response(BookingSerializer(booking).data)


class BookingRescheduleView(APIView):
    @extend_schema(
        operation_id="bookings_reschedule",
        summary="Перенести бронирование",
        tags=["Бронирования"],
        request=RescheduleSerializer,
        responses=BookingSerializer,
    )
    def post(self, request, booking_id):
        booking = get_booking_for_member(actor=request.user, booking_id=booking_id)
        serializer = RescheduleSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        booking = reschedule_booking(
            actor=request.user, booking=booking, **serializer.validated_data
        )
        return Response(BookingSerializer(booking).data)


class BookingCancelView(APIView):
    @extend_schema(
        operation_id="bookings_cancel",
        summary="Отменить бронирование",
        tags=["Бронирования"],
        request=CancelSerializer,
        responses=BookingSerializer,
    )
    def post(self, request, booking_id):
        booking = get_booking_for_member(actor=request.user, booking_id=booking_id)
        serializer = CancelSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        booking = cancel_booking(
            actor=request.user,
            booking=booking,
            reason=serializer.validated_data.get("reason", ""),
        )
        return Response(BookingSerializer(booking).data)


class BookingOverrideCancelView(APIView):
    @extend_schema(
        operation_id="bookings_override_cancel",
        summary="Принудительно отменить бронирование",
        tags=["Бронирования"],
        request=OverrideCancelSerializer,
        responses=BookingSerializer,
    )
    def post(self, request, booking_id):
        booking = get_booking_for_member(actor=request.user, booking_id=booking_id)
        serializer = OverrideCancelSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        booking = cancel_booking(
            actor=request.user,
            booking=booking,
            reason=serializer.validated_data["reason"],
            override=True,
        )
        return Response(BookingSerializer(booking).data)


class MyScheduleView(APIView):
    @extend_schema(
        operation_id="my_schedule",
        summary="Получить личное расписание",
        tags=["Бронирования"],
        parameters=[ScheduleFilterSerializer],
        responses=BookingSerializer(many=True),
    )
    def get(self, request):
        serializer = ScheduleFilterSerializer(data=request.query_params)
        serializer.is_valid(raise_exception=True)
        bookings = my_schedule(actor=request.user, **serializer.validated_data)
        return Response(BookingSerializer(bookings, many=True).data)
