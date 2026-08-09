import re

from django.db import transaction
from django.utils import timezone

from .models import (
    CustomUser,
    Notification,
    Report,
    ReportForward,
    ReportForwardToadmin,
    ReportTimeline,
)


OFFICER_LEVELS = {
    'village_chairman': 'street',
    'ward_executive': 'ward',
    'staff': 'municipal',
    'municipal_officer': 'municipal',
}

TERMINAL_STATUSES = {'closed', 'rejected'}

ACTION_RULES = {
    'accept': {
        'allowed': {'submitted', 'forwarded_to_ward', 'forwarded_to_municipal', 'clarification_requested'},
        'status': 'under_review',
    },
    'request_clarification': {
        'allowed': {'submitted', 'under_review', 'verified', 'in_progress'},
        'status': 'clarification_requested',
        'comment_required': True,
    },
    'add_note': {
        'allowed': set(dict(Report.STATUS_CHOICES)) - TERMINAL_STATUSES,
        'comment_required': True,
    },
    'verify': {
        'allowed': {'submitted', 'under_review', 'clarification_requested', 'in_progress'},
        'status': 'verified',
    },
    'forward_to_ward': {
        'allowed': {'under_review', 'clarification_requested', 'verified'},
        'status': 'forwarded_to_ward',
        'level': 'ward',
        'actor_level': 'street',
    },
    'forward_to_municipal': {
        'allowed': {'forwarded_to_ward', 'under_review', 'clarification_requested', 'verified'},
        'status': 'forwarded_to_municipal',
        'level': 'municipal',
        'actor_level': 'ward',
    },
    'start_work': {
        'allowed': {'submitted', 'forwarded_to_ward', 'forwarded_to_municipal', 'under_review', 'verified'},
        'status': 'in_progress',
    },
    'resolve': {
        'allowed': {'under_review', 'verified', 'in_progress'},
        'status': 'resolved',
        'level': 'completed',
        'comment_required': True,
    },
    'close': {
        'allowed': {'resolved'},
        'status': 'closed',
        'level': 'completed',
    },
    'reject': {
        'allowed': {'submitted', 'forwarded_to_ward', 'forwarded_to_municipal', 'under_review', 'verified'},
        'status': 'rejected',
        'level': 'completed',
        'comment_required': True,
    },
}

ACTION_MESSAGES = {
    'accept': 'Your report has been accepted for review.',
    'request_clarification': 'An officer needs more information about your report.',
    'add_note': 'A progress update was added to your report.',
    'verify': 'Your report has been verified.',
    'forward_to_ward': 'Your report has been forwarded to the ward office.',
    'forward_to_municipal': 'Your report has been forwarded to the municipal office.',
    'start_work': 'Work on your report has started.',
    'resolve': 'Your report has been resolved.',
    'close': 'Your report has been closed.',
    'reject': 'Your report could not be progressed.',
}


class ReportWorkflowError(Exception):
    pass


def normalize_location(value):
    value = re.sub(r'\(.*?\)', '', value or '')
    return ' '.join(value.lower().split())


def actor_can_access_report(actor, report):
    level = OFFICER_LEVELS.get(getattr(actor, 'role', None))
    if not level:
        return False
    if report.current_level == 'completed':
        return report.assigned_to_id == actor.id
    if report.current_level != level:
        return False
    if report.assigned_to_id:
        return report.assigned_to_id == actor.id
    if level == 'street':
        officer_street = normalize_location(actor.street.name if actor.street else '')
        report_street = normalize_location(report.street or report.street_name_backup)
        return bool(officer_street and officer_street in report_street)
    if level == 'ward':
        return (
            ReportForward.objects.filter(report=report, to_user=actor).exists()
            or bool(actor.ward and normalize_location(actor.ward.name) in normalize_location(report.district))
        )
    return actor.role in {'staff', 'municipal_officer'}


def actor_can_view_report(actor, report):
    if getattr(actor, 'role', None) == 'staff' or actor_can_access_report(actor, report):
        return True
    return (
        ReportTimeline.objects.filter(report=report, performed_by=actor).exists()
        or ReportForward.objects.filter(report=report, from_user=actor).exists()
        or ReportForward.objects.filter(report=report, to_user=actor).exists()
        or ReportForwardToadmin.objects.filter(report=report, from_user=actor).exists()
        or ReportForwardToadmin.objects.filter(report=report, to_user=actor).exists()
    )


def _forward_target(actor, destination_level, requested_target=None):
    if requested_target is not None:
        expected_roles = {
            'ward': {'ward_executive'},
            'municipal': {'staff', 'municipal_officer'},
        }[destination_level]
        if requested_target.role not in expected_roles:
            raise ReportWorkflowError('The selected officer does not belong to the destination office.')
        if actor.registered_by_id and requested_target.id != actor.registered_by_id:
            raise ReportWorkflowError('The selected officer is not linked to your office.')
        return requested_target

    linked_officer = actor.registered_by
    expected_roles = {
        'ward': {'ward_executive'},
        'municipal': {'staff', 'municipal_officer'},
    }[destination_level]
    if linked_officer and linked_officer.role in expected_roles:
        return linked_officer
    raise ReportWorkflowError(f'No {destination_level} officer is linked to your account.')


@transaction.atomic
def reconcile_legacy_ward_handoff(forward_record):
    """Repair canonical workflow fields for handoffs created by the legacy endpoint."""
    report = Report.objects.select_for_update().get(pk=forward_record.report_id)
    if report.current_level not in {'street', 'ward'}:
        return report

    old_status = report.status
    old_level = report.current_level
    update_fields = []
    if report.current_level == 'street':
        report.current_level = 'ward'
        report.status = 'forwarded_to_ward'
        update_fields.extend(('current_level', 'status'))
    elif report.status == 'submitted':
        report.status = 'forwarded_to_ward'
        update_fields.append('status')
    if old_level == 'street' and report.assigned_to_id != forward_record.to_user_id:
        report.assigned_to_id = forward_record.to_user_id
        update_fields.append('assigned_to')
    elif report.assigned_to_id is None:
        report.assigned_to_id = forward_record.to_user_id
        update_fields.append('assigned_to')

    if update_fields:
        update_fields.append('updated_at')
        report.save(update_fields=update_fields)
    if old_level == 'street' and not ReportTimeline.objects.filter(
        report=report,
        action='forward_to_ward',
        to_level='ward',
    ).exists():
        ReportTimeline.objects.create(
            report=report,
            action='forward_to_ward',
            from_status=old_status,
            to_status='forwarded_to_ward',
            from_level='street',
            to_level='ward',
            performed_by=forward_record.from_user,
            performed_by_role=getattr(forward_record.from_user, 'role', ''),
            public_comment=ACTION_MESSAGES['forward_to_ward'],
            metadata={'assigned_to_id': forward_record.to_user_id},
        )
    return report


@transaction.atomic
def perform_report_action(
    *, report_id, actor, action, public_comment='', internal_comment='', priority=None, target=None
):
    if action not in ACTION_RULES:
        raise ReportWorkflowError('Unsupported report action.')

    report = Report.objects.select_for_update().get(pk=report_id)
    actor_level = OFFICER_LEVELS.get(getattr(actor, 'role', None))
    if not actor_level:
        raise ReportWorkflowError('Only a street, ward, or municipal officer can work on a report.')
    if not actor_can_access_report(actor, report):
        raise ReportWorkflowError('This report is not assigned to your office.')

    rule = ACTION_RULES[action]
    if rule.get('actor_level') and rule['actor_level'] != actor_level:
        raise ReportWorkflowError(f'Only the {rule["actor_level"]} office can perform this action.')
    if report.status not in rule['allowed']:
        raise ReportWorkflowError(
            f'This action is not allowed while the report status is {report.get_status_display()}.'
        )
    public_comment = (public_comment or '').strip()
    internal_comment = (internal_comment or '').strip()
    if rule.get('comment_required') and not public_comment:
        raise ReportWorkflowError('A message for the reporter is required for this action.')

    old_status = report.status
    old_level = report.current_level
    new_status = rule.get('status', old_status)
    new_level = rule.get('level', old_level)
    assignee = report.assigned_to

    if new_level in {'ward', 'municipal'} and new_level != old_level:
        assignee = _forward_target(actor, new_level, target)
        if new_level == 'ward':
            ReportForward.objects.get_or_create(
                report=report,
                from_user=actor,
                to_user=assignee,
            )
        else:
            ReportForwardToadmin.objects.get_or_create(
                report=report,
                from_user=actor,
                to_user=assignee,
                defaults={'message': public_comment},
            )
    elif new_level == 'completed':
        assignee = actor
    elif action == 'accept' and assignee is None:
        assignee = actor

    report.status = new_status
    report.current_level = new_level
    report.assigned_to = assignee
    if priority:
        report.priority = priority
    if new_status == 'resolved':
        report.resolved_at = timezone.now()
    report.save(update_fields=(
        'status', 'current_level', 'assigned_to', 'priority', 'resolved_at', 'updated_at'
    ))

    timeline = ReportTimeline.objects.create(
        report=report,
        action=action,
        from_status=old_status,
        to_status=new_status,
        from_level=old_level,
        to_level=new_level,
        performed_by=actor,
        performed_by_role=actor.role,
        public_comment=public_comment or ACTION_MESSAGES[action],
        internal_comment=internal_comment,
        metadata={'assigned_to_id': assignee.id if assignee else None},
    )

    if report.user_id:
        Notification.objects.create(
            user=report.user,
            message=f'Report {report.report_id}: {timeline.public_comment}',
        )
    return report, timeline
