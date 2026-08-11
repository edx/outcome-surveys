"""
Tests for `send_follow_up_segment_events_for_passed_learners` management command.
"""

from datetime import timedelta
from unittest import TestCase, mock
from unittest.mock import patch

import pytest
from django.core.management import call_command
from django.core.management.base import CommandError
from django.utils import timezone

from outcome_surveys.constants import (
    SEGMENT_LEARNER_PASSED_COURSE_FIRST_TIME_EVENT_TYPE,
    SEGMENT_LEARNER_PASSED_COURSE_FIRST_TIME_FOLLOW_UP_EVENT_TYPE,
)
from outcome_surveys.management.commands import send_follow_up_segment_events_for_passed_learners
from outcome_surveys.models import LearnerCourseEvent

CMD_MODULE = 'outcome_surveys.management.commands.send_follow_up_segment_events_for_passed_learners'


@pytest.mark.django_db
class TestSendFollowupSegmentEventsForPassedLearnersCommand(TestCase):
    """Tests `send_follow_up_segment_events_for_passed_learners` management command."""

    def setUp(self):
        super().setUp()
        self.command = send_follow_up_segment_events_for_passed_learners.Command()
        self.course_id = 'course-v1:edX+DemoX+Demo_Course'

        self.today = timezone.now().date()
        self.yesterday = timezone.now().date() - timedelta(days=1)
        self.test_data = [
            {
                'user_id': 100,
                'course_id': self.course_id,
                'data': {
                    'LMS_ENROLLMENT_ID': 1001,
                    'COURSE_TITLE': 'An introduction to Calculus',
                    'COURSE_ORG_NAME': 'MathX',
                },
                'follow_up_date': self.today,
                'event_type': SEGMENT_LEARNER_PASSED_COURSE_FIRST_TIME_EVENT_TYPE,
            },
            {
                'user_id': 200,
                'course_id': self.course_id,
                'data': {
                    'LMS_ENROLLMENT_ID': 2001,
                    'COURSE_TITLE': 'An introduction to Python',
                    'COURSE_ORG_NAME': 'PythonX',
                },
                'follow_up_date': self.today,
                'event_type': SEGMENT_LEARNER_PASSED_COURSE_FIRST_TIME_EVENT_TYPE,
            },
            {
                'user_id': 222,
                'course_id': self.course_id,
                'data': {
                    'LMS_ENROLLMENT_ID': 2221,
                    'COURSE_TITLE': 'An introduction to Python',
                    'COURSE_ORG_NAME': 'PythonX',
                },
                'follow_up_date': self.today,
                'event_type': SEGMENT_LEARNER_PASSED_COURSE_FIRST_TIME_EVENT_TYPE,
                'already_sent': True,
            },
            {
                'user_id': 300,
                'course_id': self.course_id,
                'data': {
                    'LMS_ENROLLMENT_ID': 3001,
                    'COURSE_TITLE': 'An introduction to Databases',
                    'COURSE_ORG_NAME': 'DatabaseX',
                },
                'follow_up_date': self.yesterday,
                'event_type': SEGMENT_LEARNER_PASSED_COURSE_FIRST_TIME_EVENT_TYPE,
            },
        ]

        for item in self.test_data:
            LearnerCourseEvent.objects.create(**item)

    def construct_event_call_data(self):
        """
        Construct segment event call data for verification.
        """
        event_call_data = []
        for item in self.test_data:
            if item.get('follow_up_date') == self.today and item.get('already_sent', False) is False:
                event_call_data.append([
                    item.get('user_id'),
                    SEGMENT_LEARNER_PASSED_COURSE_FIRST_TIME_FOLLOW_UP_EVENT_TYPE,
                    item.get('data'),
                ])
        return event_call_data

    @patch('outcome_surveys.management.commands.send_follow_up_segment_events_for_passed_learners.track')
    def test_command_dry_run(self, segment_track_mock):
        call_command(self.command, '--dry-run')
        segment_track_mock.assert_has_calls([])

    @patch('outcome_surveys.management.commands.send_follow_up_segment_events_for_passed_learners.track')
    def test_command(self, segment_track_mock):
        already_sent_records = LearnerCourseEvent.objects.filter(already_sent=True)
        assert already_sent_records.count() == 1
        assert already_sent_records.first().user_id == 222
        already_sent_records_ids = list(already_sent_records.values_list('id', flat=True))

        call_command(self.command)
        expected_segment_event_calls = [mock.call(*event_data) for event_data in self.construct_event_call_data()]
        segment_track_mock.assert_has_calls(expected_segment_event_calls)

        # verify that correct records were upddated in table
        already_sent_records = LearnerCourseEvent.objects.filter(already_sent=True)
        assert already_sent_records.count() == 3
        triggered_event_user_ids = already_sent_records.exclude(
            id__in=already_sent_records_ids
        ).values_list('user_id', flat=True)
        assert list(triggered_event_user_ids) == [100, 200]


@pytest.mark.django_db
class TestSendFollowUpSegmentEventsDedup(TestCase):
    """Tests for the learner/course dedup and batch-boundary handling in the command."""

    def setUp(self):
        super().setUp()
        self.today = timezone.now().date()

    def _create_event(self, user_id, course_id):
        """
        Create a follow up event scheduled for today.
        """
        return LearnerCourseEvent.objects.create(
            user_id=user_id,
            course_id=course_id,
            data={'LMS_ENROLLMENT_ID': 1, 'COURSE_TITLE': 'Demo', 'COURSE_ORG_NAME': 'edX'},
            follow_up_date=self.today,
            event_type=SEGMENT_LEARNER_PASSED_COURSE_FIRST_TIME_EVENT_TYPE,
        )

    @patch('outcome_surveys.management.commands.send_follow_up_segment_events_for_passed_learners.track')
    def test_duplicate_rows_fire_only_one_event(self, segment_track_mock):
        self._create_event(1, 'course-v1:edX+DemoX+Demo_Course')
        self._create_event(1, 'course-v1:edX+DemoX+Demo_Course')

        call_command('send_follow_up_segment_events_for_passed_learners')

        assert segment_track_mock.call_count == 1
        assert LearnerCourseEvent.objects.filter(already_sent=True).count() == 2
        assert LearnerCourseEvent.objects.filter(already_sent=False).count() == 0

    @patch('outcome_surveys.management.commands.send_follow_up_segment_events_for_passed_learners.track')
    def test_duplicate_rows_across_batches_fire_only_one_event(self, segment_track_mock):
        batch_size = send_follow_up_segment_events_for_passed_learners.BATCH_SIZE
        for user_id in range(1, batch_size + 1):
            self._create_event(user_id, 'course-v1:edX+DemoX+Demo_Course')
        # duplicate of the very first learner, ordered last by id so it lands in the second batch
        self._create_event(1, 'course-v1:edX+DemoX+Demo_Course')

        call_command('send_follow_up_segment_events_for_passed_learners')

        assert segment_track_mock.call_count == batch_size
        assert LearnerCourseEvent.objects.filter(already_sent=False).count() == 0

    @patch('outcome_surveys.management.commands.send_follow_up_segment_events_for_passed_learners.track')
    def test_processes_every_record_beyond_one_batch(self, segment_track_mock):
        batch_size = send_follow_up_segment_events_for_passed_learners.BATCH_SIZE
        total = batch_size * 2 + 200
        for user_id in range(1, total + 1):
            self._create_event(user_id, 'course-v1:edX+DemoX+Demo_Course')

        call_command('send_follow_up_segment_events_for_passed_learners')

        assert segment_track_mock.call_count == total
        assert LearnerCourseEvent.objects.filter(already_sent=False).count() == 0

    @patch('outcome_surveys.management.commands.send_follow_up_segment_events_for_passed_learners.track')
    def test_dry_run_does_not_mark_duplicate_rows_sent(self, segment_track_mock):
        self._create_event(1, 'course-v1:edX+DemoX+Demo_Course')
        self._create_event(1, 'course-v1:edX+DemoX+Demo_Course')

        call_command('send_follow_up_segment_events_for_passed_learners', '--dry-run')

        assert segment_track_mock.call_count == 0
        assert LearnerCourseEvent.objects.filter(already_sent=True).count() == 0

    @patch('outcome_surveys.management.commands.send_follow_up_segment_events_for_passed_learners.track')
    def test_duplicate_rows_use_the_earliest_scheduled_payload(self, segment_track_mock):
        earliest = self._create_event(1, 'course-v1:edX+DemoX+Demo_Course')
        earliest.data = {'LMS_ENROLLMENT_ID': 111, 'COURSE_TITLE': 'Demo', 'COURSE_ORG_NAME': 'edX'}
        earliest.save()
        later = self._create_event(1, 'course-v1:edX+DemoX+Demo_Course')
        later.data = {'LMS_ENROLLMENT_ID': None, 'COURSE_TITLE': 'Demo', 'COURSE_ORG_NAME': 'edX'}
        later.save()

        call_command('send_follow_up_segment_events_for_passed_learners')

        segment_track_mock.assert_called_once_with(
            1, SEGMENT_LEARNER_PASSED_COURSE_FIRST_TIME_FOLLOW_UP_EVENT_TYPE, earliest.data
        )

    @patch('outcome_surveys.management.commands.send_follow_up_segment_events_for_passed_learners.track')
    def test_does_not_resend_a_row_sent_by_an_overlapping_run(self, segment_track_mock):
        event = self._create_event(1, 'course-v1:edX+DemoX+Demo_Course')
        real_filter = LearnerCourseEvent.objects.filter

        def filter_side_effect(*args, **kwargs):
            if kwargs.get('id__in'):
                real_filter(id=event.id).update(already_sent=True)
            return real_filter(*args, **kwargs)

        with mock.patch.object(LearnerCourseEvent.objects, 'filter', side_effect=filter_side_effect):
            call_command('send_follow_up_segment_events_for_passed_learners')

        assert segment_track_mock.call_count == 0


@pytest.mark.django_db
class TestSendFollowUpSegmentEventsTrackAvailability(TestCase):
    """Tests for the `track` availability guard in `send_follow_up_segment_events_for_passed_learners`."""

    @patch(f'{CMD_MODULE}.track', None)
    def test_raises_when_track_unavailable_and_not_dry_run(self):
        with pytest.raises(CommandError):
            call_command('send_follow_up_segment_events_for_passed_learners')

    @patch(f'{CMD_MODULE}.track', None)
    def test_dry_run_does_not_require_track(self):
        call_command('send_follow_up_segment_events_for_passed_learners', '--dry-run')
