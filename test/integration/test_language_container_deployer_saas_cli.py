from __future__ import annotations
from typing import Optional, Any
from contextlib import ExitStack
import time
import os

import pytest
from click.testing import CliRunner

import pyexasol
from exasol.python_extension_common.deployment.language_container_deployer_cli import (
    SAAS_ACCOUNT_ID_ENVIRONMENT_VARIABLE,
    SAAS_DATABASE_ID_ENVIRONMENT_VARIABLE,
    SAAS_TOKEN_ENVIRONMENT_VARIABLE,
)

from test.utils.revert_language_settings import revert_language_settings
from test.utils.db_utils import (create_schema, assert_udf_running)


TEST_SCHEMA = "PEC_DEPLOYER_TESTS_CLI"
TEST_LANGUAGE_ALIAS = "PYTHON3_PEC_TESTS_CLI"


def call_language_definition_deployer_cli(func,
                                          language_alias: str,
                                          url: str,
                                          account_id: str,
                                          database_id: str,
                                          token: str,
                                          connection_params: dict[str, Any],
                                          container_path: Optional[str] = None,
                                          version: Optional[str] = None,
                                          use_ssl_cert_validation: bool = False):

    os.environ[SAAS_ACCOUNT_ID_ENVIRONMENT_VARIABLE] = account_id
    os.environ[SAAS_DATABASE_ID_ENVIRONMENT_VARIABLE] = database_id
    os.environ[SAAS_TOKEN_ENVIRONMENT_VARIABLE] = token

    args_list = [
        "language-container",
        "--saas-url", url,
        "--path-in-bucket", "container",
        "--dsn", connection_params['dsn'],
        "--db-user", connection_params['user'],
        "--db-pass", connection_params['password'],
        "--language-alias", language_alias
    ]
    if use_ssl_cert_validation:
        args_list += [
            "--use-ssl-cert-validation"
        ]
    else:
        args_list += [
            "--no-use-ssl-cert-validation"
        ]
    if version:
        args_list += [
            "--version", version,
        ]
    if container_path:
        args_list += [
            "--container-file", container_path,
        ]
    runner = CliRunner()
    result = runner.invoke(func, args_list)
    return result


@pytest.mark.saas
def test_language_container_deployer_cli_with_container_file(
        saas_host: str,
        saas_token: str,
        saas_account_id: str,
        operational_saas_database_id: str,
        saas_connection_params: dict[str, Any],
        container_path: str,
        main_func
):
    with ExitStack() as stack:
        pyexasol_connection = stack.enter_context(pyexasol.connect(**saas_connection_params, compression=True))
        stack.enter_context(revert_language_settings(pyexasol_connection))
        create_schema(pyexasol_connection, TEST_SCHEMA)
        result = call_language_definition_deployer_cli(main_func,
                                                       container_path=container_path,
                                                       language_alias=TEST_LANGUAGE_ALIAS,
                                                       url=saas_host,
                                                       account_id=saas_account_id,
                                                       database_id=operational_saas_database_id,
                                                       token=saas_token,
                                                       connection_params=saas_connection_params)
        assert result.exit_code == 0
        assert result.exception is None
        assert result.stdout == ""

        # Need to give the SaaS BucketFS some time to digest the language container.
        # The required time is somewhere between 20 seconds and 5 minutes.
        time.sleep(300.)
        # In order to check that the uploaded container works we need a new pyexasol connection.
        # The deployer should have activated the language container at the system level but that would
        # not affect pre-existing sessions.
        new_connection = stack.enter_context(pyexasol.connect(**saas_connection_params, compression=True))
        assert_udf_running(new_connection, TEST_LANGUAGE_ALIAS, TEST_SCHEMA)
