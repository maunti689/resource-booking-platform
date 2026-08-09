from django.shortcuts import get_object_or_404
from drf_spectacular.utils import extend_schema
from rest_framework import status
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.audit.models import AuditEvent
from apps.organizations.models import Membership, Organization
from apps.organizations.serializers import (
    AuditEventSerializer,
    MembershipCreateSerializer,
    MembershipRoleSerializer,
    MembershipSerializer,
    OrganizationSerializer,
    OrganizationUpdateSerializer,
)
from apps.organizations.services import (
    MANAGEMENT_ROLES,
    add_member,
    create_organization,
    membership_for,
    remove_member,
    require_role,
    update_member_role,
    update_organization,
)


class OrganizationListCreateView(APIView):
    @extend_schema(
        operation_id="organizations_list",
        summary="Получить организации пользователя",
        tags=["Организации"],
        responses=OrganizationSerializer(many=True),
    )
    def get(self, request):
        organizations = Organization.objects.filter(memberships__user=request.user).distinct()
        return Response(OrganizationSerializer(organizations, many=True).data)

    @extend_schema(
        operation_id="organizations_create",
        summary="Создать организацию",
        tags=["Организации"],
        request=OrganizationSerializer,
        responses={201: OrganizationSerializer},
    )
    def post(self, request):
        serializer = OrganizationSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        organization = create_organization(actor=request.user, **serializer.validated_data)
        return Response(OrganizationSerializer(organization).data, status=status.HTTP_201_CREATED)


class OrganizationDetailView(APIView):
    @extend_schema(
        operation_id="organizations_retrieve",
        summary="Получить организацию",
        tags=["Организации"],
        responses=OrganizationSerializer,
    )
    def get(self, request, organization_id):
        organization = get_object_or_404(Organization, pk=organization_id)
        membership_for(request.user, organization)
        return Response(OrganizationSerializer(organization).data)

    @extend_schema(
        operation_id="organizations_update",
        summary="Изменить настройки организации",
        tags=["Организации"],
        request=OrganizationUpdateSerializer,
        responses=OrganizationSerializer,
    )
    def patch(self, request, organization_id):
        organization = get_object_or_404(Organization, pk=organization_id)
        serializer = OrganizationUpdateSerializer(organization, data=request.data, partial=True)
        serializer.is_valid(raise_exception=True)
        organization = update_organization(
            actor=request.user,
            organization=organization,
            changes=serializer.validated_data,
        )
        return Response(OrganizationSerializer(organization).data)


class MembershipListCreateView(APIView):
    def get_organization(self, organization_id):
        return get_object_or_404(Organization, pk=organization_id)

    @extend_schema(
        operation_id="organization_members_list",
        summary="Получить участников организации",
        tags=["Участники"],
        responses=MembershipSerializer(many=True),
    )
    def get(self, request, organization_id):
        organization = self.get_organization(organization_id)
        membership_for(request.user, organization)
        memberships = organization.memberships.select_related("user")
        return Response(MembershipSerializer(memberships, many=True).data)

    @extend_schema(
        operation_id="organization_members_create",
        summary="Добавить участника",
        tags=["Участники"],
        request=MembershipCreateSerializer,
        responses={201: MembershipSerializer},
    )
    def post(self, request, organization_id):
        organization = self.get_organization(organization_id)
        serializer = MembershipCreateSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        membership = add_member(
            actor=request.user, organization=organization, **serializer.validated_data
        )
        return Response(MembershipSerializer(membership).data, status=status.HTTP_201_CREATED)


class MembershipDetailView(APIView):
    def get_objects(self, organization_id, membership_id):
        organization = get_object_or_404(Organization, pk=organization_id)
        membership = get_object_or_404(Membership, pk=membership_id)
        return organization, membership

    @extend_schema(
        operation_id="organization_member_update",
        summary="Изменить роль участника",
        tags=["Участники"],
        request=MembershipRoleSerializer,
        responses=MembershipSerializer,
    )
    def patch(self, request, organization_id, membership_id):
        organization, membership = self.get_objects(organization_id, membership_id)
        serializer = MembershipRoleSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        membership = update_member_role(
            actor=request.user,
            organization=organization,
            membership=membership,
            role=serializer.validated_data["role"],
        )
        return Response(MembershipSerializer(membership).data)

    @extend_schema(
        operation_id="organization_member_delete",
        summary="Удалить участника",
        tags=["Участники"],
        responses={204: None},
    )
    def delete(self, request, organization_id, membership_id):
        organization, membership = self.get_objects(organization_id, membership_id)
        remove_member(actor=request.user, organization=organization, membership=membership)
        return Response(status=status.HTTP_204_NO_CONTENT)


class AuditEventListView(APIView):
    @extend_schema(
        operation_id="organization_audit_list",
        summary="Получить журнал действий",
        tags=["Аудит"],
        responses=AuditEventSerializer(many=True),
    )
    def get(self, request, organization_id):
        organization = get_object_or_404(Organization, pk=organization_id)
        require_role(request.user, organization, MANAGEMENT_ROLES)
        events = AuditEvent.objects.filter(organization=organization).select_related("actor")[:200]
        return Response(AuditEventSerializer(events, many=True).data)
