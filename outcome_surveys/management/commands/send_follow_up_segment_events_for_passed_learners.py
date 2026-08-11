"""
Send segment events for passed learners so that Braze can send 90 day follow up email.
"""

import logging

from django.core.management.base import BaseCommand, CommandError
from django.utils import timezone

from outcome_surveys.constants import (
    SEGMENT_LEARNER_PASSED_COURSE_FIRST_TIME_EVENT_TYPE,
    SEGMENT_LEARNER_PASSED_COURSE_FIRST_TIME_FOLLOW_UP_EVENT_TYPE,
)
from outcome_surveys.models import LearnerCourseEvent
from outcome_surveys.utils import optional_lms_import

track = optional_lms_import('common.djangoapps.track.segment', 'track')

log = logging.getLogger(__name__)

BATCH_SIZE = 500


class Command(BaseCommand):
    """
    Example usage:
        $ ./manage.py send_follow_up_segment_events_for_passed_learners
    """

    help = 'Send follow up segment events for passed learners.'

    def add_arguments(self, parser):
        parser.add_argument(
            '--dry-run',
            action='store_true',
            dest='dry_run',
            default=False,
            help='Dry Run, print log messages without firing the segment event.',
        )

    def handle(self, *args, **options):
        should_fire_event = not options['dry_run']
        if should_fire_event and track is None:
            raise CommandError(
                "[OUTCOME SURVEYS] Segment 'track' is unavailable in this environment. "
                "Run with --dry-run, or check that common.djangoapps.track.segment is "
                "importable here."
            )

        log_prefix = '[SEND_FOLLOW_UP_SEGMENT_EVENTS_FOR_PASSED_LEARNERS]'
        if not should_fire_event:
            log_prefix = '[DRY RUN]'

        follow_up_event_ids = []
        log.info(f'{log_prefix} Command started.')

        today = timezone.now().date()

        # Stream with keyset pagination to avoid loading all IDs into memory.
        # Dedupe by (user_id, course_id) to prevent duplicate segment events.
        handled_learner_courses = set()
        last_id = 0

        while True:
            batch_ids = list(
                LearnerCourseEvent.objects.filter(
                    follow_up_date=today,
                    event_type=SEGMENT_LEARNER_PASSED_COURSE_FIRST_TIME_EVENT_TYPE,
                    already_sent=False,
                    id__gt=last_id,
                ).order_by('id').values_list('id', flat=True)[:BATCH_SIZE]
            )

            if not batch_ids:
                break

            processed_event_record_ids = []

            # Re-check already_sent to guard against concurrent sends.
            for follow_up_event in LearnerCourseEvent.objects.filter(
                id__in=batch_ids, already_sent=False,
            ).order_by('id'):
                # Advance past every row the query returns, duplicate or not: keyset
                # pagination only makes progress if `id__gt=last_id` moves forward on every
                # iteration, so a batch that ends in duplicates must not leave it behind -
                # otherwise the next iteration re-fetches the same rows forever.
                last_id = follow_up_event.id
                learner_course = (follow_up_event.user_id, follow_up_event.course_id)

                if learner_course in handled_learner_courses:
                    # Mark duplicate as sent, but don't fire a second event.
                    if should_fire_event:
                        processed_event_record_ids.append(follow_up_event.id)
                    log.info(
                        "%s Skipping duplicate follow up event. Id: [%s], User: [%s], Course: [%s]",
                        log_prefix,
                        follow_up_event.id,
                        follow_up_event.user_id,
                        follow_up_event.course_id,
                    )
                    continue

                handled_learner_courses.add(learner_course)

                if should_fire_event:
                    track(
                        follow_up_event.user_id,
                        SEGMENT_LEARNER_PASSED_COURSE_FIRST_TIME_FOLLOW_UP_EVENT_TYPE,
                        follow_up_event.data
                    )
                    processed_event_record_ids.append(follow_up_event.id)

                follow_up_event_ids.append(follow_up_event.id)

                log.info(
                    "%s %s for passed learner. Event: [%s], Data: [%s]",
                    log_prefix,
                    "Segment event fired" if should_fire_event else "Segment event would be fired",
                    SEGMENT_LEARNER_PASSED_COURSE_FIRST_TIME_FOLLOW_UP_EVENT_TYPE,
                    follow_up_event.data
                )

            # Flush per batch rather than once at the end: if the command is interrupted
            # partway through a long run, only the in-flight batch is at risk of being
            # resent on retry, not every event fired since the run started.
            if processed_event_record_ids:
                LearnerCourseEvent.objects.filter(id__in=processed_event_record_ids).update(already_sent=True)

        log.info(
            "%s Command completed. %s for %d events. Sample ids: [%s]",
            log_prefix,
            "Segment event triggered" if should_fire_event else "Segment event would be triggered",
            len(follow_up_event_ids),
            follow_up_event_ids[:10]
        )
