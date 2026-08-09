from django.db.models.signals import post_save
from django.dispatch import receiver

from .models import CustomUser, Report, ReportTimeline
from .report_workflow import normalize_location


def _street_leader_for(report):
    report_street = normalize_location(report.street or report.street_name_backup)
    if not report_street:
        return None
    leaders = CustomUser.objects.filter(
        role='village_chairman',
        street__isnull=False,
    ).select_related('street').order_by('id')
    return next(
        (
            leader for leader in leaders
            if normalize_location(leader.street.name) in report_street
        ),
        None,
    )


@receiver(post_save, sender=Report)
def create_initial_report_timeline(sender, instance, created, **kwargs):
    if not created:
        return
    leader = _street_leader_for(instance)
    if leader:
        Report.objects.filter(pk=instance.pk).update(assigned_to=leader)
        instance.assigned_to = leader
    ReportTimeline.objects.get_or_create(
        report=instance,
        action='submit',
        defaults={
            'from_status': 'submitted',
            'to_status': 'submitted',
            'from_level': 'street',
            'to_level': 'street',
            'performed_by': instance.user,
            'performed_by_role': getattr(instance.user, 'role', '') if instance.user else '',
            'public_comment': 'Your report was submitted and sent to the street office.',
            'metadata': {'assigned_to_id': leader.id if leader else None},
        },
    )
