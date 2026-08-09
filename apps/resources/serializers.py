from rest_framework import serializers

from apps.resources.models import AvailabilityRule, BlackoutPeriod, Resource


class ResourceSerializer(serializers.ModelSerializer):
    class Meta:
        model = Resource
        fields = [
            "id",
            "organization",
            "name",
            "resource_type",
            "capacity",
            "timezone",
            "is_active",
            "availability_version",
            "created_at",
            "updated_at",
        ]
        read_only_fields = [
            "id",
            "organization",
            "availability_version",
            "created_at",
            "updated_at",
        ]


class ResourceUpdateSerializer(serializers.ModelSerializer):
    class Meta:
        model = Resource
        fields = ["name", "resource_type", "capacity", "timezone", "is_active"]
        extra_kwargs = {
            "name": {"required": False},
            "resource_type": {"required": False},
            "capacity": {"required": False},
            "timezone": {"required": False},
            "is_active": {"required": False},
        }


class AvailabilityRuleSerializer(serializers.ModelSerializer):
    class Meta:
        model = AvailabilityRule
        fields = ["id", "resource", "weekday", "start_time", "end_time"]
        read_only_fields = ["id", "resource"]

    def validate(self, attrs):
        if attrs["end_time"] <= attrs["start_time"]:
            raise serializers.ValidationError("Время окончания должно быть позже времени начала")
        return attrs


class BlackoutSerializer(serializers.ModelSerializer):
    resource_id = serializers.PrimaryKeyRelatedField(
        source="resource", queryset=Resource.objects.all(), write_only=True
    )
    resource = ResourceSerializer(read_only=True)
    created_by = serializers.CharField(source="created_by.username", read_only=True)

    class Meta:
        model = BlackoutPeriod
        fields = [
            "id",
            "resource_id",
            "resource",
            "start_at",
            "end_at",
            "reason",
            "created_by",
            "created_at",
        ]
        read_only_fields = ["id", "created_by", "created_at"]

    def validate(self, attrs):
        if attrs["end_at"] <= attrs["start_at"]:
            raise serializers.ValidationError("Дата окончания должна быть позже даты начала")
        return attrs


class AvailabilityQuerySerializer(serializers.Serializer):
    date = serializers.DateField()
    duration_minutes = serializers.IntegerField(min_value=1)
    capacity = serializers.IntegerField(min_value=1, required=False)
    resource_id = serializers.IntegerField(min_value=1, required=False)


class AvailabilitySlotSerializer(serializers.Serializer):
    start_at = serializers.DateTimeField()
    end_at = serializers.DateTimeField()


class ResourceAvailabilitySerializer(serializers.Serializer):
    resource_id = serializers.IntegerField()
    resource_name = serializers.CharField()
    timezone = serializers.CharField()
    slots = AvailabilitySlotSerializer(many=True)
