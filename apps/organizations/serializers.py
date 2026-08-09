from django.contrib.auth import get_user_model
from rest_framework import serializers

from apps.audit.models import AuditEvent
from apps.organizations.models import Membership, Organization


class OrganizationSerializer(serializers.ModelSerializer):
    max_booking_duration_minutes = serializers.IntegerField(
        min_value=1, max_value=1440, required=False
    )

    class Meta:
        model = Organization
        fields = [
            "id",
            "name",
            "slug",
            "max_booking_duration_minutes",
            "created_at",
        ]
        read_only_fields = ["id", "created_at"]


class OrganizationUpdateSerializer(serializers.ModelSerializer):
    max_booking_duration_minutes = serializers.IntegerField(
        min_value=1, max_value=1440, required=False
    )

    class Meta:
        model = Organization
        fields = ["name", "max_booking_duration_minutes"]
        extra_kwargs = {"name": {"required": False}}


class MembershipSerializer(serializers.ModelSerializer):
    username = serializers.CharField(source="user.username", read_only=True)
    email = serializers.EmailField(source="user.email", read_only=True)

    class Meta:
        model = Membership
        fields = ["id", "username", "email", "role", "created_at"]
        read_only_fields = ["id", "created_at", "username", "email"]


class MembershipCreateSerializer(serializers.Serializer):
    username = serializers.CharField(max_length=150)
    role = serializers.ChoiceField(choices=Membership.Role.choices)

    def validate_username(self, value):
        if not get_user_model().objects.filter(username=value).exists():
            raise serializers.ValidationError("Пользователь не существует")
        return value


class MembershipRoleSerializer(serializers.Serializer):
    role = serializers.ChoiceField(choices=Membership.Role.choices)


class AuditEventSerializer(serializers.ModelSerializer):
    actor = serializers.CharField(source="actor.username", read_only=True)

    class Meta:
        model = AuditEvent
        fields = [
            "id",
            "event_type",
            "object_type",
            "object_id",
            "actor",
            "metadata",
            "created_at",
        ]
        read_only_fields = fields
