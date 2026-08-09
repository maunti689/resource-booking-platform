from django.urls import path

from apps.resources.views import (
    AvailabilityRuleListCreateView,
    AvailabilitySearchView,
    BlackoutListCreateView,
    ResourceDetailView,
    ResourceListCreateView,
)

urlpatterns = [
    path(
        "organizations/<int:organization_id>/resources",
        ResourceListCreateView.as_view(),
        name="resources",
    ),
    path(
        "organizations/<int:organization_id>/resources/<int:resource_id>",
        ResourceDetailView.as_view(),
        name="resource-detail",
    ),
    path(
        "organizations/<int:organization_id>/resources/<int:resource_id>/availability-rules",
        AvailabilityRuleListCreateView.as_view(),
        name="availability-rules",
    ),
    path(
        "organizations/<int:organization_id>/blackouts",
        BlackoutListCreateView.as_view(),
        name="blackouts",
    ),
    path(
        "organizations/<int:organization_id>/availability",
        AvailabilitySearchView.as_view(),
        name="availability-search",
    ),
]
