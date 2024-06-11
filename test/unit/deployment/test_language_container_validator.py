import pytest
from datetime import datetime, timedelta
from unittest.mock import create_autospec, patch

from pyexasol import ExaConnection

from exasol.python_extension_common.deployment.language_container_validator import wait_language_container


@pytest.fixture(scope='module')
def mock_pyexasol_conn() -> ExaConnection:
    return create_autospec(ExaConnection)


class TimeChecker:
    def __init__(self, duration: timedelta):
        self._set_time = datetime.now() + duration

    def check_time(self, *args, **kwargs):
        if datetime.now() < self._set_time:
            raise RuntimeError


@patch('exasol.python_extension_common.deployment.language_container_validator.validate_language_container')
def test_wait_language_container_success(mock_validate_slc, mock_pyexasol_conn):
    tc = TimeChecker(timedelta(milliseconds=200))
    mock_validate_slc.side_effect = tc.check_time
    wait_language_container(mock_pyexasol_conn,
                            'xyz',
                            timeout=timedelta(milliseconds=400),
                            interval=timedelta(milliseconds=50))


@patch('exasol.python_extension_common.deployment.language_container_validator.validate_language_container')
def test_wait_language_container_failure(mock_validate_slc, mock_pyexasol_conn):
    tc = TimeChecker(timedelta(milliseconds=400))
    mock_validate_slc.side_effect = tc.check_time
    with pytest.raises(Exception):
        wait_language_container(mock_pyexasol_conn,
                                'xyz',
                                timeout=timedelta(milliseconds=200),
                                interval=timedelta(milliseconds=50))
