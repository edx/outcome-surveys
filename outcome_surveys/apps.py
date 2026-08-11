"""
outcome_surveys Django application initialization.
"""

from django.apps import AppConfig
from edx_django_utils.plugins.constants import PluginSignals


class OutcomeSurveysConfig(AppConfig):
    """
    Configuration for the outcome_surveys Django application.
    """

    name = 'outcome_surveys'
    label = 'outcome_surveys'
    verbose_name = "Outcome Surveys"
    plugin_app = {
        PluginSignals.CONFIG: {
            'lms.djangoapp': {
                PluginSignals.RECEIVERS: [
                    {
                        PluginSignals.SIGNAL_PATH: 'lms.djangoapps.grades.signals.signals'
                                                   '.SCHEDULE_FOLLOW_UP_SEGMENT_EVENT_FOR_COURSE_PASSED_FIRST_TIME',
                        PluginSignals.RECEIVER_FUNC_NAME: 'schedule_course_passed_first_time_follow_up_segment_event',
                    },
                    {
                        # Certificates issued via the certificate allowlist (used by externally
                        # graded courses, e.g. the CS50 family) never emit
                        # SCHEDULE_FOLLOW_UP_SEGMENT_EVENT_FOR_COURSE_PASSED_FIRST_TIME because no
                        # passing grade is ever computed for those learners. COURSE_CERT_AWARDED
                        # fires for any passing certificate regardless of how it was generated, so
                        # it covers the gap.
                        PluginSignals.SIGNAL_PATH: 'openedx.core.djangoapps.signals.signals.COURSE_CERT_AWARDED',
                        PluginSignals.RECEIVER_FUNC_NAME: 'schedule_course_certificate_awarded_follow_up_segment_event',
                    },
                ],
            },
        },
    }
