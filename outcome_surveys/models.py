"""
Database models for outcome_surveys.
"""
from django.db import models
from jsonfield import JSONField
# from django.db import models
from model_utils.models import TimeStampedModel
from opaque_keys.edx.django.models import CourseKeyField

from outcome_surveys.constants import SEGMENT_LEARNER_PASSED_COURSE_FIRST_TIME_EVENT_TYPE


class LearnerCourseEvent(TimeStampedModel):
    """
    Learner Course Event model for tracking passed event sent to learners.

    .. no_pii:
    """

    user_id = models.IntegerField()
    course_id = CourseKeyField(blank=False, null=False, max_length=255)
    data = JSONField()
    follow_up_date = models.DateField()

    EVENT_CHOICES = [
        (SEGMENT_LEARNER_PASSED_COURSE_FIRST_TIME_EVENT_TYPE, SEGMENT_LEARNER_PASSED_COURSE_FIRST_TIME_EVENT_TYPE),
    ]
    event_type = models.CharField(
        max_length=255,
        choices=EVENT_CHOICES,
        default=SEGMENT_LEARNER_PASSED_COURSE_FIRST_TIME_EVENT_TYPE,
    )
    already_sent = models.BooleanField(default=False)

    class Meta:
        """
        Meta class for LearnerCourseEvent.
        """

        app_label = "outcome_surveys"
        indexes = [
            models.Index(fields=['follow_up_date']),
            models.Index(fields=['created']),
        ]

    def __str__(self):
        """
        Get a string representation of this model instance.
        """
        # TODO: return a string appropriate for the data fields
        return '<LearnerCourseEvent, ID: {}>'.format(self.id)
