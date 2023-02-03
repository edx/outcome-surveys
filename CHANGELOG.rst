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
