#!/usr/bin/env python
"""
Tests for the `outcome_surveys` signals module.
"""

from datetime import timedelta
from unittest import TestCase
from unittest.mock import Mock, patch

import pytest
from django.utils import timezone
from opaque_keys.edx.locator import CourseLocator

from outcome_surveys.constants import (
    OUTCOME_SURVEYS_FOLLOW_UP_DAYS_DEFAULT,
    SEGMENT_LEARNER_ACHIEVED_LEARNING_TIME_EVENT_TYPE,
    SEGMENT_LEARNER_PASSED_COURSE_FIRST_TIME_EVENT_TYPE,
)
from outcome_surveys.models import LearnerCourseEvent
from outcome_surveys.signals import (
    schedule_course_certificate_awarded_follow_up_segment_event,
    schedule_course_passed_first_time_follow_up_segment_event,
)
from outcome_surveys.utils import optional_lms_import

LMS_MODULE = 'common.djangoapps.student.models'


class TestOptionalLmsImport(TestCase):
    """Tests for the optional LMS imports the signal handlers depend on."""

    def test_returns_the_attribute_when_the_module_is_importable(self):
        assert optional_lms_import('outcome_surveys.constants', 'ENROLLMENT_TYPE_B2C') == 'B2C'

    def test_returns_none_when_the_lms_package_is_absent(self):
        assert optional_lms_import(LMS_MODULE, 'CourseEnrollment') is None

    def test_returns_none_when_an_intermediate_package_is_absent(self):
        # Python reports the missing top-level package, not the full dotted path.
        with patch('outcome_surveys.utils.import_module') as import_module_mock:
            import_module_mock.side_effect = ModuleNotFoundError(
                "No module named 'common.djangoapps'", name='common.djangoapps'
            )
            assert optional_lms_import(LMS_MODULE, 'CourseEnrollment') is None

    def test_reraises_when_a_dependency_inside_the_module_is_missing(self):
        with patch('outcome_surveys.utils.import_module') as import_module_mock:
            import_module_mock.side_effect = ModuleNotFoundError(
                "No module named 'some_uninstalled_dependency'", name='some_uninstalled_dependency'
            )
            with pytest.raises(ModuleNotFoundError, match='some_uninstalled_dependency'):
                optional_lms_import(LMS_MODULE, 'CourseEnrollment')

    def test_reraises_when_a_similarly_named_module_is_missing(self):
        with patch('outcome_surveys.utils.import_module') as import_module_mock:
            import_module_mock.side_effect = ModuleNotFoundError(
                "No module named 'commonmark'", name='commonmark'
            )
            with pytest.raises(ModuleNotFoundError, match='commonmark'):
                optional_lms_import(LMS_MODULE, 'CourseEnrollment')

    def test_reraises_when_the_module_has_no_such_attribute(self):
        with pytest.raises(AttributeError):
            optional_lms_import('outcome_surveys.constants', 'NO_SUCH_CONSTANT')


@pytest.mark.django_db
class TestSignals(TestCase):
    """Tests class for outcome_surveys signals."""

    def setUp(self):
        super().setUp()

        self.user_id = 1222
        self.course_id = 'course-v1:edX+DemoX+Demo_Course'
        self.event_properties = {
            'LMS_ENROLLMENT_ID': 2221,
            'COURSE_TITLE': 'edX Demo Course',
            'COURSE_ORG_NAME': 'edX',
        }
        self.follow_up_date = timezone.now().date() + timedelta(days=OUTCOME_SURVEYS_FOLLOW_UP_DAYS_DEFAULT)

    def test_handle_segment_event_fired_for_learner_passed_course_first_time(self):
        schedule_course_passed_first_time_follow_up_segment_event(
            None,
            self.user_id,
            self.course_id,
            self.event_properties
        )

        assert LearnerCourseEvent.objects.count() == 1

        learner_course_event = LearnerCourseEvent.objects.get(
            user_id=self.user_id,
            course_id=self.course_id,
            follow_up_date=self.follow_up_date,
            event_type=SEGMENT_LEARNER_PASSED_COURSE_FIRST_TIME_EVENT_TYPE
        )

        assert learner_course_event.data == self.event_properties

    def test_does_not_reschedule_when_event_already_exists(self):
        LearnerCourseEvent.objects.create(
            user_id=self.user_id,
            course_id=self.course_id,
            data=self.event_properties,
            follow_up_date=self.follow_up_date,
            event_type=SEGMENT_LEARNER_PASSED_COURSE_FIRST_TIME_EVENT_TYPE,
        )

        schedule_course_passed_first_time_follow_up_segment_event(
            None,
            self.user_id,
            self.course_id,
            self.event_properties
        )

        assert LearnerCourseEvent.objects.filter(
            user_id=self.user_id,
            course_id=self.course_id,
            event_type=SEGMENT_LEARNER_PASSED_COURSE_FIRST_TIME_EVENT_TYPE,
        ).count() == 1


@pytest.mark.django_db
class TestCertificateAwardedSignal(TestCase):
    """Tests for `schedule_course_certificate_awarded_follow_up_segment_event`."""

    def setUp(self):
        super().setUp()

        self.user = Mock(id=1222)
        self.course_key = CourseLocator('edX', 'CS50X', 'Demo_Course')
        self.follow_up_date = timezone.now().date() + timedelta(days=OUTCOME_SURVEYS_FOLLOW_UP_DAYS_DEFAULT)
        self.passed_first_time_event_properties = {
            'LMS_ENROLLMENT_ID': 2221,
            'COURSE_TITLE': 'CS50 for edX',
            'COURSE_ORG_NAME': 'edX',
        }

    def test_schedules_follow_up_event_for_allowlist_certificate(self):
        schedule_course_certificate_awarded_follow_up_segment_event(
            None,
            user=self.user,
            course_key=self.course_key,
            mode='verified',
            status='downloadable',
        )

        learner_course_event = LearnerCourseEvent.objects.get(
            user_id=self.user.id,
            course_id=self.course_key,
            follow_up_date=self.follow_up_date,
            event_type=SEGMENT_LEARNER_PASSED_COURSE_FIRST_TIME_EVENT_TYPE,
        )

        assert learner_course_event.data['COURSE_ORG_NAME'] == 'edX'

    @patch('outcome_surveys.signals.CourseEnrollment')
    @patch('outcome_surveys.signals.CourseOverview')
    def test_populates_course_title_and_enrollment_id_from_lms_models(
        self, course_overview_mock, course_enrollment_mock
    ):
        course_overview_mock.objects.filter.return_value.values_list.return_value.first.return_value = (
            'CS50 for edX'
        )
        course_enrollment_mock.objects.filter.return_value.values_list.return_value.first.return_value = 4242

        schedule_course_certificate_awarded_follow_up_segment_event(
            None,
            user=self.user,
            course_key=self.course_key,
            mode='verified',
            status='downloadable',
        )

        learner_course_event = LearnerCourseEvent.objects.get(
            user_id=self.user.id,
            course_id=self.course_key,
            event_type=SEGMENT_LEARNER_PASSED_COURSE_FIRST_TIME_EVENT_TYPE,
        )
        assert learner_course_event.data['COURSE_TITLE'] == 'CS50 for edX'
        assert learner_course_event.data['LMS_ENROLLMENT_ID'] == 4242
        course_overview_mock.objects.filter.assert_called_once_with(id=self.course_key)
        course_enrollment_mock.objects.filter.assert_called_once_with(
            user_id=self.user.id, course_id=self.course_key
        )

    def test_does_not_duplicate_an_existing_follow_up_event(self):
        LearnerCourseEvent.objects.create(
            user_id=self.user.id,
            course_id=self.course_key,
            data={},
            follow_up_date=self.follow_up_date,
            event_type=SEGMENT_LEARNER_PASSED_COURSE_FIRST_TIME_EVENT_TYPE,
        )

        schedule_course_certificate_awarded_follow_up_segment_event(
            None,
            user=self.user,
            course_key=self.course_key,
            mode='verified',
            status='downloadable',
        )

        assert LearnerCourseEvent.objects.filter(
            user_id=self.user.id,
            course_id=self.course_key,
            event_type=SEGMENT_LEARNER_PASSED_COURSE_FIRST_TIME_EVENT_TYPE,
        ).count() == 1

    def test_repeat_certificate_save_does_not_reschedule(self):
        for _ in range(3):
            schedule_course_certificate_awarded_follow_up_segment_event(
                None,
                user=self.user,
                course_key=self.course_key,
                mode='verified',
                status='downloadable',
            )

        assert LearnerCourseEvent.objects.filter(
            user_id=self.user.id,
            course_id=self.course_key,
            event_type=SEGMENT_LEARNER_PASSED_COURSE_FIRST_TIME_EVENT_TYPE,
        ).count() == 1

    def test_certificate_award_after_passed_first_time_does_not_duplicate(self):
        schedule_course_passed_first_time_follow_up_segment_event(
            None,
            self.user.id,
            self.course_key,
            self.passed_first_time_event_properties,
        )
        schedule_course_certificate_awarded_follow_up_segment_event(
            None,
            user=self.user,
            course_key=self.course_key,
            mode='verified',
            status='downloadable',
        )

        follow_up_events = LearnerCourseEvent.objects.filter(
            user_id=self.user.id,
            course_id=self.course_key,
            event_type=SEGMENT_LEARNER_PASSED_COURSE_FIRST_TIME_EVENT_TYPE,
        )
        assert follow_up_events.count() == 1
        assert follow_up_events.first().data == self.passed_first_time_event_properties

    def test_passed_first_time_after_certificate_award_does_not_duplicate(self):
        schedule_course_certificate_awarded_follow_up_segment_event(
            None,
            user=self.user,
            course_key=self.course_key,
            mode='verified',
            status='downloadable',
        )
        schedule_course_passed_first_time_follow_up_segment_event(
            None,
            self.user.id,
            self.course_key,
            self.passed_first_time_event_properties,
        )

        follow_up_events = LearnerCourseEvent.objects.filter(
            user_id=self.user.id,
            course_id=self.course_key,
            event_type=SEGMENT_LEARNER_PASSED_COURSE_FIRST_TIME_EVENT_TYPE,
        )
        assert follow_up_events.count() == 1
        # The certificate handler's payload, not the `passed_first_time` one.
        assert follow_up_events.first().data['LMS_ENROLLMENT_ID'] is None

    def _fire_certificate_awarded(self):
        schedule_course_certificate_awarded_follow_up_segment_event(
            None,
            user=self.user,
            course_key=self.course_key,
            mode='verified',
            status='downloadable',
        )

    def _fire_passed_first_time(self):
        schedule_course_passed_first_time_follow_up_segment_event(
            None,
            self.user.id,
            self.course_key,
            self.passed_first_time_event_properties,
        )

    @patch('outcome_surveys.signals._follow_up_event_already_scheduled', return_value=False)
    def test_interleaved_handlers_do_not_duplicate(self, already_scheduled_mock):
        for first, second in (
            (self._fire_certificate_awarded, self._fire_passed_first_time),
            (self._fire_passed_first_time, self._fire_certificate_awarded),
        ):
            with self.subTest(first=first.__name__, second=second.__name__):
                LearnerCourseEvent.objects.all().delete()

                first()
                second()

                assert LearnerCourseEvent.objects.filter(
                    user_id=self.user.id,
                    course_id=self.course_key,
                    event_type=SEGMENT_LEARNER_PASSED_COURSE_FIRST_TIME_EVENT_TYPE,
                ).count() == 1

        assert already_scheduled_mock.call_count == 2

    def test_schedules_despite_unrelated_learning_time_event(self):
        LearnerCourseEvent.objects.create(
            user_id=self.user.id,
            course_id=self.course_key,
            data={},
            follow_up_date=self.follow_up_date,
            event_type=SEGMENT_LEARNER_ACHIEVED_LEARNING_TIME_EVENT_TYPE,
        )

        schedule_course_certificate_awarded_follow_up_segment_event(
            None,
            user=self.user,
            course_key=self.course_key,
            mode='verified',
            status='downloadable',
        )

        assert LearnerCourseEvent.objects.filter(
            user_id=self.user.id,
            course_id=self.course_key,
            event_type=SEGMENT_LEARNER_PASSED_COURSE_FIRST_TIME_EVENT_TYPE,
        ).count() == 1
