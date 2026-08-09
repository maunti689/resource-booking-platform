from django.shortcuts import get_object_or_404
from drf_spectacular.utils import extend_schema
from rest_framework import status
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.organizations.models import Organization
from apps.organizations.services import membership_for
from apps.resources.models import AvailabilityRule, BlackoutPeriod, Resource
from apps.resources.serializers import (
    AvailabilityQuerySerializer,
    AvailabilityRuleSerializer,
    BlackoutSerializer,
    ResourceAvailabilitySerializer,
    ResourceSerializer,
    ResourceUpdateSerializer,
)
from apps.resources.services import (
    create_blackout,
    create_resource,
    deactivate_resource,
    find_available_slots,
    get_resource_for_member,
    update_resource,
    upsert_availability_rule,
)


class ResourceListCreateView(APIView):
    def get_organization(self, organization_id):
        return get_object_or_404(Organization, pk=organization_id)

    @extend_schema(
        operation_id="resources_list",
        summary="Получить ресурсы организации",
        tags=["Ресурсы"],
        responses=ResourceSerializer(many=True),
    )
    def get(self, request, organization_id):
        organization = self.get_organization(organization_id)
        membership_for(request.user, organization)
        resources = Resource.objects.filter(organization=organization)
        return Response(ResourceSerializer(resources, many=True).data)

    @extend_schema(
        operation_id="resources_create",
        summary="Создать ресурс",
        tags=["Ресурсы"],
        request=ResourceSerializer,
        responses={201: ResourceSerializer},
    )
    def post(self, request, organization_id):
        organization = self.get_organization(organization_id)
        serializer = ResourceSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        resource = create_resource(
            actor=request.user,
            organization=organization,
            name=serializer.validated_data["name"],
            resource_type=serializer.validated_data.get("resource_type", Resource.Type.ROOM),
            capacity=serializer.validated_data.get("capacity", 1),
            timezone_name=serializer.validated_data.get("timezone", "UTC"),
        )
        return Response(ResourceSerializer(resource).data, status=status.HTTP_201_CREATED)


class ResourceDetailView(APIView):
    @extend_schema(
        operation_id="resources_retrieve",
        summary="Получить ресурс",
        tags=["Ресурсы"],
        responses=ResourceSerializer,
    )
    def get(self, request, organization_id, resource_id):
        organization = get_object_or_404(Organization, pk=organization_id)
        resource = get_resource_for_member(
            actor=request.user, organization=organization, resource_id=resource_id
        )
        return Response(ResourceSerializer(resource).data)

    @extend_schema(
        operation_id="resources_delete",
        summary="Архивировать ресурс",
        tags=["Ресурсы"],
        responses={204: None},
    )
    def delete(self, request, organization_id, resource_id):
        organization = get_object_or_404(Organization, pk=organization_id)
        resource = get_resource_for_member(
            actor=request.user,
            organization=organization,
            resource_id=resource_id,
        )
        deactivate_resource(
            actor=request.user,
            organization=organization,
            resource=resource,
        )
        return Response(status=status.HTTP_204_NO_CONTENT)

    @extend_schema(
        operation_id="resources_update",
        summary="Изменить ресурс",
        tags=["Ресурсы"],
        request=ResourceUpdateSerializer,
        responses=ResourceSerializer,
    )
    def patch(self, request, organization_id, resource_id):
        organization = get_object_or_404(Organization, pk=organization_id)
        resource = get_resource_for_member(
            actor=request.user, organization=organization, resource_id=resource_id
        )
        serializer = ResourceUpdateSerializer(resource, data=request.data, partial=True)
        serializer.is_valid(raise_exception=True)
        resource = update_resource(
            actor=request.user,
            organization=organization,
            resource=resource,
            changes=serializer.validated_data,
        )
        return Response(ResourceSerializer(resource).data)


class AvailabilityRuleListCreateView(APIView):
    def get_objects(self, request, organization_id, resource_id):
        organization = get_object_or_404(Organization, pk=organization_id)
        resource = get_resource_for_member(
            actor=request.user, organization=organization, resource_id=resource_id
        )
        return organization, resource

    @extend_schema(
        operation_id="availability_rules_list",
        summary="Получить рабочие часы ресурса",
        tags=["Доступность"],
        responses=AvailabilityRuleSerializer(many=True),
    )
    def get(self, request, organization_id, resource_id):
        _, resource = self.get_objects(request, organization_id, resource_id)
        rules = AvailabilityRule.objects.filter(resource=resource)
        return Response(AvailabilityRuleSerializer(rules, many=True).data)

    @extend_schema(
        operation_id="availability_rules_upsert",
        summary="Создать или обновить рабочие часы",
        tags=["Доступность"],
        request=AvailabilityRuleSerializer,
        responses={201: AvailabilityRuleSerializer},
    )
    def post(self, request, organization_id, resource_id):
        organization, resource = self.get_objects(request, organization_id, resource_id)
        serializer = AvailabilityRuleSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        rule = upsert_availability_rule(
            actor=request.user,
            organization=organization,
            resource=resource,
            **serializer.validated_data,
        )
        return Response(AvailabilityRuleSerializer(rule).data, status=status.HTTP_201_CREATED)


class BlackoutListCreateView(APIView):
    def get_organization(self, organization_id):
        return get_object_or_404(Organization, pk=organization_id)

    @extend_schema(
        operation_id="blackouts_list",
        summary="Получить периоды недоступности",
        tags=["Доступность"],
        responses=BlackoutSerializer(many=True),
    )
    def get(self, request, organization_id):
        organization = self.get_organization(organization_id)
        membership_for(request.user, organization)
        blackouts = BlackoutPeriod.objects.filter(
            resource__organization=organization
        ).select_related("resource", "created_by")
        return Response(BlackoutSerializer(blackouts, many=True).data)

    @extend_schema(
        operation_id="blackouts_create",
        summary="Создать период недоступности",
        tags=["Доступность"],
        request=BlackoutSerializer,
        responses={201: BlackoutSerializer},
    )
    def post(self, request, organization_id):
        organization = self.get_organization(organization_id)
        serializer = BlackoutSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        blackout = create_blackout(
            actor=request.user,
            organization=organization,
            resource=serializer.validated_data["resource"],
            start_at=serializer.validated_data["start_at"],
            end_at=serializer.validated_data["end_at"],
            reason=serializer.validated_data["reason"],
        )
        return Response(BlackoutSerializer(blackout).data, status=status.HTTP_201_CREATED)


class AvailabilitySearchView(APIView):
    @extend_schema(
        operation_id="availability_search",
        summary="Найти свободные интервалы",
        tags=["Доступность"],
        parameters=[AvailabilityQuerySerializer],
        responses=ResourceAvailabilitySerializer(many=True),
    )
    def get(self, request, organization_id):
        organization = get_object_or_404(Organization, pk=organization_id)
        serializer = AvailabilityQuerySerializer(data=request.query_params)
        serializer.is_valid(raise_exception=True)
        result = find_available_slots(
            actor=request.user,
            organization=organization,
            target_date=serializer.validated_data.pop("date"),
            **serializer.validated_data,
        )
        return Response(result)
