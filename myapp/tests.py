from django.test import TestCase
from django.urls import reverse
from rest_framework.test import APIClient

from .models import (
    CustomUser,
    Report,
    ReportForward,
    ReportForwardToadmin,
    ReportHistory,
    Street,
    Ward,
)
from .report_workflow import ReportWorkflowError, actor_can_view_report, perform_report_action
from .serializers import ReportTrackingSerializer


class ReportWorkflowTests(TestCase):
    def setUp(self):
        self.ward = Ward.objects.create(name='Mikocheni')
        self.street = Street.objects.create(name='Mikocheni A', ward=self.ward)
        self.municipal = CustomUser.objects.create_user(
            username='municipal', role='municipal_officer', password='test-pass'
        )
        self.ward_officer = CustomUser.objects.create_user(
            username='ward', role='ward_executive', ward=self.ward,
            registered_by=self.municipal, password='test-pass'
        )
        self.street_leader = CustomUser.objects.create_user(
            username='street', role='village_chairman', street=self.street,
            ward=self.ward, registered_by=self.ward_officer, password='test-pass'
        )
        self.reporter = CustomUser.objects.create_user(
            username='reporter', role='user', password='test-pass'
        )
        self.report = Report.objects.create(
            description='Waste has blocked the drainage.',
            district='Mikocheni',
            street='Mikocheni A (Mikocheni)',
            user=self.reporter,
        )

    def test_new_report_gets_initial_timeline_and_street_assignment(self):
        self.report.refresh_from_db()

        self.assertEqual(self.report.status, 'submitted')
        self.assertEqual(self.report.current_level, 'street')
        self.assertEqual(self.report.assigned_to, self.street_leader)
        event = self.report.timeline.get()
        self.assertEqual(event.action, 'submit')
        self.assertEqual(event.to_level, 'street')

    def test_report_can_move_through_all_three_office_levels(self):
        perform_report_action(
            report_id=self.report.pk,
            actor=self.street_leader,
            action='accept',
        )
        perform_report_action(
            report_id=self.report.pk,
            actor=self.street_leader,
            action='forward_to_ward',
        )
        self.report.refresh_from_db()
        self.assertEqual(self.report.current_level, 'ward')
        self.assertEqual(self.report.assigned_to, self.ward_officer)
        self.assertTrue(ReportForward.objects.filter(report=self.report).exists())
        self.assertTrue(actor_can_view_report(self.street_leader, self.report))

        perform_report_action(
            report_id=self.report.pk,
            actor=self.ward_officer,
            action='accept',
        )
        perform_report_action(
            report_id=self.report.pk,
            actor=self.ward_officer,
            action='forward_to_municipal',
        )
        self.report.refresh_from_db()
        self.assertEqual(self.report.status, 'forwarded_to_municipal')
        self.assertEqual(self.report.current_level, 'municipal')
        self.assertEqual(self.report.assigned_to, self.municipal)
        self.assertTrue(ReportForwardToadmin.objects.filter(report=self.report).exists())
        self.assertTrue(actor_can_view_report(self.street_leader, self.report))

        perform_report_action(
            report_id=self.report.pk,
            actor=self.municipal,
            action='start_work',
        )
        perform_report_action(
            report_id=self.report.pk,
            actor=self.municipal,
            action='resolve',
            public_comment='The drainage was cleared and inspected.',
        )
        perform_report_action(
            report_id=self.report.pk,
            actor=self.municipal,
            action='close',
        )
        self.report.refresh_from_db()
        self.assertEqual(self.report.status, 'closed')
        self.assertEqual(self.report.current_level, 'completed')
        self.assertEqual(
            list(self.report.timeline.values_list('action', flat=True)),
            ['submit', 'accept', 'forward_to_ward', 'accept', 'forward_to_municipal', 'start_work', 'resolve', 'close'],
        )

    def test_required_public_update_and_internal_note_privacy(self):
        with self.assertRaises(ReportWorkflowError):
            perform_report_action(
                report_id=self.report.pk,
                actor=self.street_leader,
                action='request_clarification',
            )

        perform_report_action(
            report_id=self.report.pk,
            actor=self.street_leader,
            action='request_clarification',
            public_comment='Please add a closer photo.',
            internal_comment='Check whether this is inside the reserve boundary.',
        )
        payload = ReportTrackingSerializer(
            Report.objects.prefetch_related('timeline__performed_by').get(pk=self.report.pk)
        ).data
        self.assertNotIn('internal_comment', payload['timeline'][-1])
        self.assertEqual(payload['timeline'][-1]['public_comment'], 'Please add a closer photo.')

    def test_street_can_forward_new_report_then_only_track_it(self):
        perform_report_action(
            report_id=self.report.pk,
            actor=self.street_leader,
            action='forward_to_ward',
        )

        self.report.refresh_from_db()
        self.assertEqual(self.report.status, 'forwarded_to_ward')
        self.assertEqual(self.report.current_level, 'ward')
        self.assertTrue(actor_can_view_report(self.street_leader, self.report))

        with self.assertRaises(ReportWorkflowError):
            perform_report_action(
                report_id=self.report.pk,
                actor=self.street_leader,
                action='resolve',
                public_comment='This must be handled by the current office.',
            )

    def test_street_confirmation_resolves_report_and_prevents_forwarding(self):
        perform_report_action(
            report_id=self.report.pk,
            actor=self.street_leader,
            action='resolve',
            public_comment='The street office has solved this report.',
        )

        self.report.refresh_from_db()
        self.assertEqual(self.report.status, 'resolved')
        self.assertEqual(self.report.current_level, 'completed')
        self.assertEqual(self.report.assigned_to, self.street_leader)
        self.assertIsNotNone(self.report.resolved_at)
        self.assertTrue(ReportHistory.objects.filter(report_id=self.report.report_id).exists())

        with self.assertRaises(ReportWorkflowError):
            perform_report_action(
                report_id=self.report.pk,
                actor=self.street_leader,
                action='forward_to_ward',
            )

        self.assertFalse(ReportForward.objects.filter(report=self.report).exists())

    def test_ward_endpoint_accepts_linked_municipal_officer_role(self):
        perform_report_action(
            report_id=self.report.pk,
            actor=self.street_leader,
            action='accept',
        )
        perform_report_action(
            report_id=self.report.pk,
            actor=self.street_leader,
            action='forward_to_ward',
        )
        forward = ReportForward.objects.get(report=self.report, to_user=self.ward_officer)
        client = APIClient()
        client.force_authenticate(user=self.ward_officer)

        response = client.post(
            reverse('forward-to-admin-from-village', kwargs={'forward_id': forward.pk}),
            {'message': 'Please continue this report at municipal level.'},
            format='json',
        )

        self.assertEqual(response.status_code, 200, response.data)
        self.report.refresh_from_db()
        self.assertEqual(self.report.status, 'forwarded_to_municipal')
        self.assertEqual(self.report.assigned_to, self.municipal)

    def test_ward_endpoint_repairs_a_legacy_street_handoff(self):
        legacy_forward = ReportForward.objects.create(
            report=self.report,
            from_user=self.street_leader,
            to_user=self.ward_officer,
        )
        client = APIClient()
        client.force_authenticate(user=self.ward_officer)

        response = client.post(
            reverse('forward-to-admin-from-village', kwargs={'forward_id': legacy_forward.pk}),
            {'message': 'Forward this legacy report to municipal.'},
            format='json',
        )

        self.assertEqual(response.status_code, 200, response.data)
        self.report.refresh_from_db()
        self.assertEqual(self.report.current_level, 'municipal')
        self.assertEqual(self.report.assigned_to, self.municipal)
        self.assertTrue(
            self.report.timeline.filter(action='forward_to_ward', to_level='ward').exists()
        )

    def test_forwarded_reports_are_tracking_only_and_resolved_reports_leave_all_queues(self):
        perform_report_action(
            report_id=self.report.pk,
            actor=self.street_leader,
            action='forward_to_ward',
        )

        street_client = APIClient()
        street_client.force_authenticate(user=self.street_leader)
        street_response = street_client.get(reverse('reports-by-street'))
        self.assertEqual(street_response.status_code, 200)
        self.assertEqual(len(street_response.data), 1)
        self.assertEqual(street_response.data[0]['current_level'], 'ward')

        ward_client = APIClient()
        ward_client.force_authenticate(user=self.ward_officer)
        ward_response = ward_client.get(reverse('forwarded-reports-for-ward'))
        self.assertEqual(ward_response.status_code, 200)
        self.assertEqual(len(ward_response.data), 1)
        self.assertEqual(ward_response.data[0]['current_level'], 'ward')

        perform_report_action(
            report_id=self.report.pk,
            actor=self.ward_officer,
            action='forward_to_municipal',
        )
        ward_response = ward_client.get(reverse('forwarded-reports-for-ward'))
        self.assertEqual(len(ward_response.data), 1)
        self.assertEqual(ward_response.data[0]['current_level'], 'municipal')
        self.assertTrue(ward_response.data[0]['forwarded_to_admin'])

        denied_response = ward_client.post(
            reverse('work-on-report', kwargs={'report_id': self.report.pk}),
            {'action': 'resolve', 'public_comment': 'Ward must no longer act.'},
            format='json',
        )
        self.assertEqual(denied_response.status_code, 400)

        perform_report_action(
            report_id=self.report.pk,
            actor=self.municipal,
            action='resolve',
            public_comment='The municipal office solved the report.',
        )

        self.assertEqual(len(street_client.get(reverse('reports-by-street')).data), 0)
        self.assertEqual(len(ward_client.get(reverse('forwarded-reports-for-ward')).data), 0)

        municipal_client = APIClient()
        municipal_client.force_authenticate(user=self.municipal)
        municipal_response = municipal_client.get(reverse('forwarded_reports_to_admin'))
        self.assertEqual(municipal_response.status_code, 200)
        self.assertEqual(len(municipal_response.data), 0)
        self.assertTrue(ReportHistory.objects.filter(report_id=self.report.report_id).exists())

    def test_unrelated_street_leader_cannot_work_on_report(self):
        other_street = Street.objects.create(name='Kawe', ward=self.ward)
        other_leader = CustomUser.objects.create_user(
            username='other', role='village_chairman', street=other_street,
            password='test-pass'
        )
        with self.assertRaises(ReportWorkflowError):
            perform_report_action(
                report_id=self.report.pk,
                actor=other_leader,
                action='accept',
            )
