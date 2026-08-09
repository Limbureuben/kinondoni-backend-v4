from django.test import TestCase

from .models import CustomUser, Report, ReportForward, ReportForwardToadmin, Street, Ward
from .report_workflow import ReportWorkflowError, perform_report_action
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
            action='forward_to_ward',
        )
        self.report.refresh_from_db()
        self.assertEqual(self.report.current_level, 'ward')
        self.assertEqual(self.report.assigned_to, self.ward_officer)
        self.assertTrue(ReportForward.objects.filter(report=self.report).exists())

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
            ['submit', 'forward_to_ward', 'accept', 'forward_to_municipal', 'start_work', 'resolve', 'close'],
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
