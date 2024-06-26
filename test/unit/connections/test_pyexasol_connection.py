from __future__ import annotations
from typing import Any
from unittest.mock import patch

import pytest

from exasol.python_extension_common.connections.pyexasol_connection import open_pyexasol_connection
from exasol.python_extension_common.deployment.language_container_deployer import get_websocket_sslopt


@pytest.fixture
def onprem_params() -> dict[str, Any]:
    return {
        'dsn': 'my_cluster:123',
        'db_user': 'the user',
        'db_pass': 'the password',
        'schema': 'fake_schema',
        'use_ssl_cert_validation': False
    }


@pytest.fixture
def saas_params() -> dict[str, Any]:
    return {
        'saas_url': 'https://saas_fake_service.com',
        'saas_account_id': 'saas_fake_account_id',
        'saas_database_name': 'saas_fake_database',
        'saas_token': 'saas_fake_pat',
        'schema': 'fake_schema',
        'use_ssl_cert_validation': True
    }


@pytest.fixture
def saas_connection_params() -> dict[str, Any]:
    return {
            "dsn": "xyz.fake_saas.exasol.com:1234",
            "user": "fake_saas_user",
            "password": "fake_saas_password"
    }


@patch('pyexasol.connect')
def test_open_pyexasol_connection_onprem(mock_connect, onprem_params):

    sslopt = get_websocket_sslopt(onprem_params['use_ssl_cert_validation'])

    open_pyexasol_connection(**onprem_params)
    mock_connect.assert_called_with(
        dsn=onprem_params['dsn'],
        user=onprem_params['db_user'],
        password=onprem_params['db_pass'],
        schema=onprem_params['schema'],
        encryption=True,
        websocket_sslopt=sslopt,
        compression=True)


@patch('exasol.saas.client.api_access.get_connection_params')
@patch('pyexasol.connect')
def test_open_pyexasol_connection_saas(mock_connect, mock_conn_params,
                                       saas_params, saas_connection_params):

    mock_conn_params.return_value = saas_connection_params
    sslopt = get_websocket_sslopt(saas_params['use_ssl_cert_validation'])

    open_pyexasol_connection(**saas_params)
    mock_connect.assert_called_with(
        dsn=saas_connection_params['dsn'],
        user=saas_connection_params['user'],
        password=saas_connection_params['password'],
        schema=saas_params['schema'],
        encryption=True,
        websocket_sslopt=sslopt,
        compression=True)
