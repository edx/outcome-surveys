"""
outcome_surveys signals.
"""
from datetime import timedelta
from logging import getLogger

from django.conf import settings
from django.utils import timezone

from outcome_surveys.constants import (
    OUTCOME_SURVEYS_FOLLOW_UP_DAYS_DEFAULT,
    SEGMENT_LEARNER_PASSED_COURSE_FIRST_TIME_EVENT_TYPE,
)
from outcome_surveys.models import LearnerCourseEvent
from outcome_surveys.utils import optional_lms_import

CourseEnrollment = optional_lms_import('common.djangoapps.student.models', 'CourseEnrollment')
CourseOverview = optional_lms_import(
    'openedx.core.djangoapps.content.course_overviews.models',
    'CourseOverview',
)

log = getLogger(__name__)


def _dedup_key(user_id, course_id):
    """
    Return the lookup kwargs identifying a learner/course's passed-first-time follow up row.
    """
    return {
        'user_id': user_id,
        'course_id': course_id,
        'event_type': SEGMENT_LEARNER_PASSED_COURSE_FIRST_TIME_EVENT_TYPE,
    }


def _follow_up_event_already_scheduled(user_id, course_id):
    """Return True if a passed-first-time follow up row already exists for this learner/course."""
    return LearnerCourseEvent.objects.filter(**_dedup_key(user_id, course_id)).exists()


def _create_follow_up_event(user_id, course_id, event_properties):
    """Schedule the follow up event once; returns follow_up_date on creation, None if it existed."""
    days = getattr(settings, 'OUTCOME_SURVEYS_FOLLOW_UP_DAYS', OUTCOME_SURVEYS_FOLLOW_UP_DAYS_DEFAULT)
    follow_up_date = timezone.now().date() + timedelta(days=days)

    __, created = LearnerCourseEvent.objects.get_or_create(
        **_dedup_key(user_id, course_id),
        defaults={
            'data': event_properties,
            'follow_up_date': follow_up_date,
        },
    )

    return follow_up_date if created else None


def schedule_course_passed_first_time_follow_up_segment_event(
    sender,
    user_id,
    course_id,
    event_properties,
    **kwargs  # pylint: disable=unused-argument
):
    """Listen for `SCHEDULE_FOLLOW_UP_SEGMENT_EVENT_FOR_COURSE_PASSED_FIRST_TIME` and schedule a follow up event."""
    log.info("[OUTCOME SURVEYS] Follow up signal received.")
    follow_up_date = _create_follow_up_event(user_id, course_id, event_properties)
    if follow_up_date is None:
        log.info(
            "[OUTCOME SURVEYS] Follow up event already scheduled. User: [%s], Course: [%s]",
            user_id,
            course_id,
        )
        return

    log.info(
        "[OUTCOME SURVEYS] Follow up event scheduled. User: [%s], Course: [%s], Enrollment: [%s], Date: [%s]",
        user_id,
        course_id,
        event_properties['LMS_ENROLLMENT_ID'],
        follow_up_date
    )


def schedule_course_certificate_awarded_follow_up_segment_event(
    sender,
    user,
    course_key,
    mode,
    status,
    **kwargs  # pylint: disable=unused-argument
):
    """Schedule a follow-up survey event on certificate award, for learners skipped by the grading path."""
    if _follow_up_event_already_scheduled(user.id, course_key):
        return

    course_title = ''
    if CourseOverview is not None:
        course_title = CourseOverview.objects.filter(id=course_key).values_list('display_name', flat=True).first()

    enrollment_id = None
    if CourseEnrollment is not None:
        enrollment_id = CourseEnrollment.objects.filter(
            user_id=user.id, course_id=course_key
        ).values_list('id', flat=True).first()

    event_properties = {
        'LMS_ENROLLMENT_ID': enrollment_id,
        'COURSE_TITLE': course_title,
        'COURSE_ORG_NAME': course_key.org,
    }
    follow_up_date = _create_follow_up_event(user.id, course_key, event_properties)
    if follow_up_date is None:
        return

    log.info(
        "[OUTCOME SURVEYS] Follow up event scheduled from certificate award. "
        "User: [%s], Course: [%s], Mode: [%s], Status: [%s], Date: [%s]",
        user.id,
        course_key,
        mode,
        status,
        follow_up_date
    )
