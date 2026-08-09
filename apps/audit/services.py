from apps.audit.models import AuditEvent


def record_event(
    *, organization, actor, event_type: str, target, metadata: dict | None = None
) -> AuditEvent:
    return AuditEvent.objects.create(
        organization=organization,
        actor=actor,
        event_type=event_type,
        object_type=target._meta.model_name,
        object_id=str(target.pk),
        metadata=metadata or {},
    )
