from django.urls import path

from apps.organizations.views import (
    AuditEventListView,
    MembershipDetailView,
    MembershipListCreateView,
    OrganizationDetailView,
    OrganizationListCreateView,
)

urlpatterns = [
    path("organizations", OrganizationListCreateView.as_view(), name="organizations"),
    path(
        "organizations/<int:organization_id>",
        OrganizationDetailView.as_view(),
        name="organization-detail",
    ),
    path(
        "organizations/<int:organization_id>/members",
        MembershipListCreateView.as_view(),
        name="organization-members",
    ),
    path(
        "organizations/<int:organization_id>/members/<int:membership_id>",
        MembershipDetailView.as_view(),
        name="organization-member-detail",
    ),
    path(
        "organizations/<int:organization_id>/audit",
        AuditEventListView.as_view(),
        name="organization-audit",
    ),
]
