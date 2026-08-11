Change Log
----------

..
   All enhancements and patches to outcome_surveys will be documented
   in this file.  It adheres to the structure of https://keepachangelog.com/ ,
   but in reStructuredText instead of Markdown (for ease of incorporation into
   Sphinx documentation and the PyPI description).

   This project adheres to Semantic Versioning (https://semver.org/).

.. There should always be an "Unreleased" section for changes pending release.

Unreleased
~~~~~~~~~~

[3.0.5]- 2026-08-07
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
* feat: schedule follow up survey event on `COURSE_CERT_AWARDED` signal, to cover
  certificates issued via the certificate allowlist (e.g. externally graded courses),
  which never trigger the existing `passed_first_time` follow up event.
* fix: guard the `passed_first_time` handler against scheduling a duplicate follow up
  event, matching the guard already used by the `COURSE_CERT_AWARDED` handler. Both
  handlers now write via `get_or_create` on `(user_id, course_id, event_type)`, so no
  work happens between the duplicate check and the insert.
* fix: narrow the optional LMS imports (`CourseEnrollment`, `CourseOverview`, `track`) so
  only the absence of the LMS package itself is tolerated. A `ModuleNotFoundError` raised
  from inside an importable LMS module is a real deployment problem and now propagates
  instead of silently leaving the handler with incomplete event metadata.
* fix: dedupe by learner/course when sending follow up segment events, so duplicate
  `LearnerCourseEvent` rows (including any already present) can no longer send a
  learner a second follow up email. Duplicate rows are marked as sent rather than
  re-fired. This replaces an earlier approach that added a unique constraint on
  `(user_id, course_id, event_type)`; the table lives in the edxapp database and
  pre-existing duplicate rows would have blocked that migration.
* fix: snapshot pending event ids before sending, so marking rows `already_sent`
  no longer shrinks the queryset mid-iteration and skips records past the first batch.

[3.0.4]- 2026-06-19
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
* feat: migrated the snowflake connectivity from username to private key

[3.0.3]- 2025-08-11
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
* temp: add logs to debug issue with `OperationalError` in `MultiChoiceResponse.save_answers`

[3.0.2]- 2025-07-29
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
* fix: use latest version of setuptools

[3.0.1]- 2025-07-08
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
* fix: publish to pypi github action

[3.0.0]- 2025-07-07
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
* feat: upgrade python version to 3.11

[2.6.0]- 2024-11-06
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
* Deprecated edx-sphinx-theme and replaced it with sphinx-book-theme

[2.5.1] - 2024-02-22
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
* Update prepared learners query

[2.5.0] - 2023-11-02
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
* Add management command to trigger segment events for learners who have achieved 30 minutes of learning

[2.4.0] - 2023-03-13
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
* Add support to delete survey responses

[2.3.1] - 2023-03-01
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
* Remove broad exception

[2.3.0] - 2023-02-27
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
* Remove null=True from char and text model fields

[2.1.0] - 2023-02-03
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
* Add uniqe constraints on table fields
* Replace `get_or_create`` with custom implementation
* Gracefully exit command upon `SurveyMonkeyDailyRateLimitConsumed` exception

[2.0.0] - 2023-02-01
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
* Django management command to import data from SurveyMonkey

[1.1.1] - 2022-09-06
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
* Add `already_sent` boolean field in `LearnerCourseEvent` model to store the state for sent events.
* Set `already_sent`` to `True` in `LearnerCourseEvent` model for each triggered event.

[1.1.0] - 2022-07-14
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
* Make follow up days configurable


[0.1.0] - 2022-07-06
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

Added
_____

* First release on PyPI.
