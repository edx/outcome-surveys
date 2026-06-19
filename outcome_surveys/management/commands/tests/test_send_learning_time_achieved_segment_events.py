"""
Tests for `send_learning_time_achieved_segment_events` management command.
"""

from unittest import TestCase, mock
from unittest.mock import call, patch

import pytest
from cryptography.hazmat.backends import default_backend
from cryptography.hazmat.primitives.asymmetric import rsa
from cryptography.hazmat.primitives.serialization import BestAvailableEncryption, Encoding, NoEncryption, PrivateFormat
from django.core.exceptions import ImproperlyConfigured
from django.core.management import call_command
from django.test import override_settings
from django.utils import timezone
from snowflake.connector import DictCursor

from outcome_surveys.constants import SEGMENT_LEARNER_ACHIEVED_LEARNING_TIME_EVENT_TYPE
from outcome_surveys.management.commands import send_learning_time_achieved_segment_events
from outcome_surveys.management.commands.tests.mock_responses import MOCK_QUERY_DATA
from outcome_surveys.models import LearnerCourseEvent

CMD_MODULE = 'outcome_surveys.management.commands.send_learning_time_achieved_segment_events'


@pytest.mark.django_db
class TestSendSegmentEventsForPreparedLearnersCommand(TestCase):
    """
    Tests `send_learning_time_achieved_segment_events` management command.
    """

    def setUp(self):
        super().setUp()
        self.command = send_learning_time_achieved_segment_events.Command()

    @staticmethod
    def generate_query_data(size=2):
        """
        Generator to return records for processing.
        """
        for i in range(0, len(MOCK_QUERY_DATA), size):
            yield MOCK_QUERY_DATA[i:i + size]

    @patch('outcome_surveys.management.commands.send_learning_time_achieved_segment_events.track')
    @mock.patch(
        'outcome_surveys.management.commands.send_learning_time_achieved_segment_events.Command.fetch_data_from_snowflake'  # nopep8 pylint: disable=line-too-long
    )
    def test_command_dry_run(self, mock_fetch_data_from_snowflake, segment_track_mock):
        """
        Verify that management command does not fire any segment event in dry run mode.
        """
        mock_fetch_data_from_snowflake.return_value = self.generate_query_data()
        mock_path = 'outcome_surveys.management.commands.send_learning_time_achieved_segment_events.log.info'

        with mock.patch(mock_path) as mock_logger:
            call_command(self.command, '--dry-run')
            segment_track_mock.assert_has_calls([])
            assert LearnerCourseEvent.objects.count() == 0

            user_ids = [record['USER_ID'] for record in MOCK_QUERY_DATA]
            mock_logger.assert_has_calls(
                [
                    call('%s Command started.', '[DRY RUN]'),
                    call('%s Processing [%s] rows', '[DRY RUN]', 2),
                    call('%s Processing %s', '[DRY RUN]', MOCK_QUERY_DATA[0]),
                    call('%s Processing %s', '[DRY RUN]', MOCK_QUERY_DATA[1]),
                    call('%s Processing completed of [%s] rows', '[DRY RUN]', 2),
                    call('%s Processing [%s] rows', '[DRY RUN]', 2),
                    call('%s Processing %s', '[DRY RUN]', MOCK_QUERY_DATA[2]),
                    call('%s Processing %s', '[DRY RUN]', MOCK_QUERY_DATA[3]),
                    call('%s Processing completed of [%s] rows', '[DRY RUN]', 2),
                    call('%s Command completed. Segment events triggered for user ids: %s', '[DRY RUN]', user_ids)
                ]
            )

    @patch('outcome_surveys.management.commands.send_learning_time_achieved_segment_events.track')
    @mock.patch(
        'outcome_surveys.management.commands.send_learning_time_achieved_segment_events.Command.fetch_data_from_snowflake'  # nopep8 pylint: disable=line-too-long
    )
    def test_command(self, mock_fetch_data_from_snowflake, segment_track_mock):
        """
        Verify that management command fires segment events with correct data.
        """
        mock_fetch_data_from_snowflake.return_value = self.generate_query_data()

        call_command(self.command)

        expected_segment_calls = [
            call(
                5000,
                SEGMENT_LEARNER_ACHIEVED_LEARNING_TIME_EVENT_TYPE,
                {'course_key': 'UUX+ITAx', 'course_title': 'Intro to Accounting'}
            ),
            call(
                5001,
                SEGMENT_LEARNER_ACHIEVED_LEARNING_TIME_EVENT_TYPE,
                {'course_key': 'BCC+ITC', 'course_title': 'Intro to Calculus'}
            ),
            call(
                5002,
                SEGMENT_LEARNER_ACHIEVED_LEARNING_TIME_EVENT_TYPE,
                {'course_key': 'ABC+CSA', 'course_title': 'Intro to Computer Architecture'}
            ),
            call(
                5003,
                SEGMENT_LEARNER_ACHIEVED_LEARNING_TIME_EVENT_TYPE,
                {'course_key': 'BCC+ITC', 'course_title': 'Intro to Quantum Computing'}
            )
        ]
        segment_track_mock.assert_has_calls(expected_segment_calls)

        sent_events = LearnerCourseEvent.objects.all()
        assert sent_events.count() == len(MOCK_QUERY_DATA)
        for record in MOCK_QUERY_DATA:
            tracked_event = LearnerCourseEvent.objects.get(user_id=record['USER_ID'])
            assert tracked_event.already_sent
            assert str(tracked_event.course_id) == record['COURSERUN_KEY']
            assert tracked_event.data == {
                'course_key': record['COURSE_KEY'],
                'course_title': record['COURSERUN_TITLE']
            }
            assert tracked_event.follow_up_date == timezone.now().date()
            assert tracked_event.event_type == SEGMENT_LEARNER_ACHIEVED_LEARNING_TIME_EVENT_TYPE


class TestBuildPrivateKeyBytes(TestCase):
    """Unit tests for _build_private_key_bytes."""

    def _generate_pem_key(self, passphrase=None):
        """Generate a real RSA PEM key, optionally encrypted with a passphrase."""
        private_key = rsa.generate_private_key(
            public_exponent=65537,
            key_size=2048,
            backend=default_backend(),
        )
        encryption = (
            BestAvailableEncryption(passphrase.encode('utf-8')) if passphrase else NoEncryption()
        )
        return private_key.private_bytes(
            encoding=Encoding.PEM,
            format=PrivateFormat.PKCS8,
            encryption_algorithm=encryption,
        ).decode('utf-8')

    def test_without_passphrase(self):
        """Returns DER bytes from an unencrypted PEM key."""
        pem = self._generate_pem_key()
        # pylint: disable-next=protected-access
        result = send_learning_time_achieved_segment_events._build_private_key_bytes(pem, None)
        self.assertIsInstance(result, bytes)
        self.assertEqual(result[0], 0x30)  # ASN.1 SEQUENCE tag — well-formed DER

    def test_with_passphrase(self):
        """Decrypts a passphrase-protected PEM key and returns DER bytes."""
        passphrase = 'test-passphrase'
        pem = self._generate_pem_key(passphrase=passphrase)
        # pylint: disable-next=protected-access
        result = send_learning_time_achieved_segment_events._build_private_key_bytes(pem, passphrase)
        self.assertIsInstance(result, bytes)
        self.assertEqual(result[0], 0x30)


class TestFetchDataFromSnowflake(TestCase):
    """Tests for Command.fetch_data_from_snowflake — private key auth and resource handling."""

    FAKE_PEM = '-----BEGIN PRIVATE KEY-----\nFAKE\n-----END PRIVATE KEY-----'

    def setUp(self):
        super().setUp()
        self.command = send_learning_time_achieved_segment_events.Command()

    def _mock_build_key(self, fake_der=b'fake-der-bytes'):
        return mock.patch(f'{CMD_MODULE}._build_private_key_bytes', return_value=fake_der)

    def _mock_connect(self):
        return mock.patch('snowflake.connector.connect')

    def _make_mock_connection(self, fetchmany_side_effect=None):
        """Build a mock Snowflake connection and cursor pair."""
        mock_cursor = mock.Mock()
        mock_cursor.fetchmany.side_effect = fetchmany_side_effect or [[]]
        mock_connection = mock.Mock()
        mock_connection.cursor.return_value = mock_cursor
        return mock_connection, mock_cursor

    # ------------------------------------------------------------------
    # ImproperlyConfigured guard-rails
    # ------------------------------------------------------------------

    @override_settings(SNOWFLAKE_SERVICE_USER=None, SNOWFLAKE_SERVICE_PRIVKEY=FAKE_PEM)
    def test_raises_when_user_missing(self):
        """ImproperlyConfigured raised when SNOWFLAKE_SERVICE_USER is absent."""
        with self.assertRaises(ImproperlyConfigured) as ctx:
            list(self.command.fetch_data_from_snowflake('[TEST]'))
        self.assertIn('SNOWFLAKE_SERVICE_USER', str(ctx.exception))

    @override_settings(SNOWFLAKE_SERVICE_USER='svc-user', SNOWFLAKE_SERVICE_PRIVKEY=None)
    def test_raises_when_privkey_missing(self):
        """ImproperlyConfigured raised when SNOWFLAKE_SERVICE_PRIVKEY is absent."""
        with self.assertRaises(ImproperlyConfigured) as ctx:
            list(self.command.fetch_data_from_snowflake('[TEST]'))
        self.assertIn('SNOWFLAKE_SERVICE_PRIVKEY', str(ctx.exception))

    # ------------------------------------------------------------------
    # Private key authentication
    # ------------------------------------------------------------------

    @override_settings(
        SNOWFLAKE_SERVICE_USER='svc-user',
        SNOWFLAKE_SERVICE_PRIVKEY=FAKE_PEM,
        SNOWFLAKE_SERVICE_PASSPHRASE='s3cr3t',
    )
    def test_connects_with_private_key_and_passphrase(self):
        """connector.connect receives private_key (not password); passphrase forwarded to _build_private_key_bytes."""
        mock_connection, _ = self._make_mock_connection()
        with self._mock_build_key(b'der-bytes') as mock_build, \
                self._mock_connect() as mock_connect:
            mock_connect.return_value = mock_connection
            list(self.command.fetch_data_from_snowflake('[TEST]'))

        mock_build.assert_called_once_with(self.FAKE_PEM, 's3cr3t')
        call_kwargs = mock_connect.call_args[1]
        self.assertEqual(call_kwargs['user'], 'svc-user')
        self.assertEqual(call_kwargs['private_key'], b'der-bytes')
        self.assertNotIn('password', call_kwargs)

    @override_settings(
        SNOWFLAKE_SERVICE_USER='svc-user',
        SNOWFLAKE_SERVICE_PRIVKEY=FAKE_PEM,
    )
    def test_connects_without_passphrase(self):
        """_build_private_key_bytes is called with passphrase=None when SNOWFLAKE_SERVICE_PASSPHRASE is unset."""
        mock_connection, _ = self._make_mock_connection()
        with self._mock_build_key() as mock_build, \
                self._mock_connect() as mock_connect:
            mock_connect.return_value = mock_connection
            list(self.command.fetch_data_from_snowflake('[TEST]'))

        mock_build.assert_called_once_with(self.FAKE_PEM, None)

    # ------------------------------------------------------------------
    # Generator behaviour and resource cleanup
    # ------------------------------------------------------------------

    @override_settings(SNOWFLAKE_SERVICE_USER='svc-user', SNOWFLAKE_SERVICE_PRIVKEY=FAKE_PEM)
    def test_yields_rows_in_batches(self):
        """Generator yields each non-empty batch and stops on an empty fetch."""
        batch1 = [{'USER_ID': 1}, {'USER_ID': 2}]
        batch2 = [{'USER_ID': 3}]
        mock_connection, _ = self._make_mock_connection(fetchmany_side_effect=[batch1, batch2, []])

        with self._mock_build_key(), self._mock_connect() as mock_connect:
            mock_connect.return_value = mock_connection
            result = list(self.command.fetch_data_from_snowflake('[TEST]'))

        self.assertEqual(result, [batch1, batch2])

    @override_settings(SNOWFLAKE_SERVICE_USER='svc-user', SNOWFLAKE_SERVICE_PRIVKEY=FAKE_PEM)
    def test_cursor_and_connection_closed_after_success(self):
        """Cursor and connection are always closed after successful iteration."""
        mock_connection, mock_cursor = self._make_mock_connection()

        with self._mock_build_key(), self._mock_connect() as mock_connect:
            mock_connect.return_value = mock_connection
            list(self.command.fetch_data_from_snowflake('[TEST]'))

        mock_cursor.close.assert_called_once()
        mock_connection.close.assert_called_once()

    @override_settings(SNOWFLAKE_SERVICE_USER='svc-user', SNOWFLAKE_SERVICE_PRIVKEY=FAKE_PEM)
    def test_cursor_and_connection_closed_on_exception(self):
        """Cursor and connection are closed even when query execution raises."""
        mock_cursor = mock.Mock()
        mock_cursor.execute.side_effect = RuntimeError('query failed')
        mock_connection = mock.Mock()
        mock_connection.cursor.return_value = mock_cursor

        with self._mock_build_key(), self._mock_connect() as mock_connect:
            mock_connect.return_value = mock_connection
            with self.assertRaises(RuntimeError):
                list(self.command.fetch_data_from_snowflake('[TEST]'))

        mock_cursor.close.assert_called_once()
        mock_connection.close.assert_called_once()

    @override_settings(SNOWFLAKE_SERVICE_USER='svc-user', SNOWFLAKE_SERVICE_PRIVKEY=FAKE_PEM)
    def test_cursor_opened_with_dict_cursor(self):
        """connection.cursor is called with DictCursor so rows are returned as dicts."""
        mock_connection, _ = self._make_mock_connection()

        with self._mock_build_key(), self._mock_connect() as mock_connect:
            mock_connect.return_value = mock_connection
            list(self.command.fetch_data_from_snowflake('[TEST]'))

        mock_connection.cursor.assert_called_once_with(DictCursor)

    @override_settings(SNOWFLAKE_SERVICE_USER='svc-user', SNOWFLAKE_SERVICE_PRIVKEY=FAKE_PEM)
    def test_logs_and_reraises_on_connection_failure(self):
        """Connection errors are logged via log.exception and then re-raised."""
        with self._mock_build_key(), \
                self._mock_connect() as mock_connect, \
                mock.patch(f'{CMD_MODULE}.log') as mock_log:
            mock_connect.side_effect = RuntimeError('auth failed')
            with self.assertRaises(RuntimeError):
                list(self.command.fetch_data_from_snowflake('[TEST]'))

        mock_log.exception.assert_called_once()
        call_args = mock_log.exception.call_args[0]
        self.assertIn('svc-user', call_args[2])
