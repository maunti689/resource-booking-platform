from rest_framework import serializers

from apps.bookings.models import Booking
from apps.resources.models import Resource


class BookingSerializer(serializers.ModelSerializer):
    resource_name = serializers.CharField(source="resource.name", read_only=True)
    resource_timezone = serializers.CharField(source="resource.timezone", read_only=True)
    owner = serializers.CharField(source="owner.username", read_only=True)
    participants = serializers.SlugRelatedField(many=True, read_only=True, slug_field="email")

    class Meta:
        model = Booking
        fields = [
            "id",
            "resource",
            "resource_name",
            "resource_timezone",
            "owner",
            "start_at",
            "end_at",
            "purpose",
            "status",
            "participants",
            "cancelled_at",
            "cancel_reason",
            "created_at",
            "updated_at",
        ]
        read_only_fields = fields


class BookingCreateSerializer(serializers.Serializer):
    resource_id = serializers.PrimaryKeyRelatedField(
        source="resource", queryset=Resource.objects.select_related("organization")
    )
    start_at = serializers.DateTimeField()
    end_at = serializers.DateTimeField()
    purpose = serializers.CharField(max_length=240)
    participants = serializers.ListField(
        child=serializers.EmailField(), required=False, allow_empty=True
    )

    def validate(self, attrs):
        if attrs["end_at"] <= attrs["start_at"]:
            raise serializers.ValidationError("Дата окончания должна быть позже даты начала")
        return attrs


class RescheduleSerializer(serializers.Serializer):
    start_at = serializers.DateTimeField()
    end_at = serializers.DateTimeField()

    def validate(self, attrs):
        if attrs["end_at"] <= attrs["start_at"]:
            raise serializers.ValidationError("Дата окончания должна быть позже даты начала")
        return attrs


class CancelSerializer(serializers.Serializer):
    reason = serializers.CharField(max_length=240, required=False, allow_blank=True)


class OverrideCancelSerializer(serializers.Serializer):
    reason = serializers.CharField(max_length=240, allow_blank=False)


class BookingFilterSerializer(serializers.Serializer):
    organization_id = serializers.IntegerField(min_value=1)
    resource_id = serializers.IntegerField(min_value=1, required=False)
    start_at = serializers.DateTimeField(required=False)
    end_at = serializers.DateTimeField(required=False)
    status = serializers.ChoiceField(choices=Booking.Status.choices, required=False)


class ScheduleFilterSerializer(serializers.Serializer):
    start_at = serializers.DateTimeField(required=False)
    end_at = serializers.DateTimeField(required=False)
