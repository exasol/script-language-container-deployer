from typing import Optional, Callable
from contextlib import ExitStack

import pytest
from urllib.parse import urlparse
from click.testing import CliRunner
from pyexasol import ExaConnection, ExaConnectionFailedError
from pytest_itde import config

from test.utils.revert_language_settings import revert_language_settings
from test.utils.db_utils import (create_schema, assert_udf_running)


TEST_SCHEMA = "PEC_DEPLOYER_TESTS_CLI"
TEST_LANGUAGE_ALIAS = "PYTHON3_PEC_TESTS_CLI"


def call_language_definition_deployer_cli(func,
                                          exasol_config: config.Exasol,
                                          bucketfs_config: config.BucketFs,
                                          language_alias: str,
                                          container_path: Optional[str] = None,
                                          version: Optional[str] = None,
                                          use_ssl_cert_validation: bool = False):
    parsed_url = urlparse(bucketfs_config.url)
    args_list = [
        "language-container",
        "--bucketfs-name", "bfsdefault",
        "--bucketfs-host", parsed_url.hostname,
        "--bucketfs-port", parsed_url.port,
        "--bucketfs-use-https", False,
        "--bucketfs-user", bucketfs_config.username,
        "--bucketfs-password", bucketfs_config.password,
        "--bucket", "default",
        "--path-in-bucket", "container",
        "--dsn", f"{exasol_config.host}:{exasol_config.port}",
        "--db-user", exasol_config.username,
        "--db-pass", exasol_config.password,
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


def test_language_container_deployer_cli_with_container_file(
        itde: config.TestConfig,
        connection_factory: Callable[[config.Exasol], ExaConnection],
        container_path: str,
        main_func
):
    with ExitStack() as stack:
        pyexasol_connection = stack.enter_context(connection_factory(itde.db))
        stack.enter_context(revert_language_settings(pyexasol_connection))
        create_schema(pyexasol_connection, TEST_SCHEMA)
        result = call_language_definition_deployer_cli(main_func,
                                                       container_path=container_path,
                                                       language_alias=TEST_LANGUAGE_ALIAS,
                                                       exasol_config=itde.db,
                                                       bucketfs_config=itde.bucketfs)
        assert result.exit_code == 0
        assert result.exception is None
        assert result.stdout == ""
        # In order to check that the uploaded container works we need a new pyexasol connection.
        # The deployer should have activated the language container at the system level but that would
        # not affect pre-existing sessions.
        new_connection = stack.enter_context(connection_factory(itde.db))
        assert_udf_running(new_connection, TEST_LANGUAGE_ALIAS, TEST_SCHEMA)


def test_language_container_deployer_cli_by_downloading_container(
        itde: config.TestConfig,
        connection_factory: Callable[[config.Exasol], ExaConnection],
        container_version: str,
        main_func
):
    with ExitStack() as stack:
        pyexasol_connection = stack.enter_context(connection_factory(itde.db))
        stack.enter_context(revert_language_settings(pyexasol_connection))
        create_schema(pyexasol_connection, TEST_SCHEMA)
        result = call_language_definition_deployer_cli(main_func,
                                                       version=container_version,
                                                       language_alias=TEST_LANGUAGE_ALIAS,
                                                       exasol_config=itde.db,
                                                       bucketfs_config=itde.bucketfs)
        assert result.exit_code == 0
        assert result.exception is None
        assert result.stdout == ""
        new_connection = stack.enter_context(connection_factory(itde.db))
        assert_udf_running(new_connection, TEST_LANGUAGE_ALIAS, TEST_SCHEMA)


def test_language_container_deployer_cli_with_missing_container_option(
        itde: config.TestConfig,
        connection_factory: Callable[[config.Exasol], ExaConnection],
        main_func
):
    with ExitStack() as stack:
        pyexasol_connection = stack.enter_context(connection_factory(itde.db))
        stack.enter_context(revert_language_settings(pyexasol_connection))
        result = call_language_definition_deployer_cli(main_func,
                                                       language_alias=TEST_LANGUAGE_ALIAS,
                                                       bucketfs_config=itde.bucketfs,
                                                       exasol_config=itde.db)
        assert result.exit_code == 1
        assert isinstance(result.exception, ValueError)


def test_language_container_deployer_cli_with_check_cert(
        itde: config.TestConfig,
        connection_factory: Callable[[config.Exasol], ExaConnection],
        container_path: str,
        main_func
):
    expected_exception_message = '[SSL: CERTIFICATE_VERIFY_FAILED]'
    with ExitStack() as stack:
        pyexasol_connection = stack.enter_context(connection_factory(itde.db))
        stack.enter_context(revert_language_settings(pyexasol_connection))
        create_schema(pyexasol_connection, TEST_SCHEMA)
        result = call_language_definition_deployer_cli(main_func,
                                                       container_path=container_path,
                                                       language_alias=TEST_LANGUAGE_ALIAS,
                                                       exasol_config=itde.db,
                                                       bucketfs_config=itde.bucketfs,
                                                       use_ssl_cert_validation=True)
        assert result.exit_code == 1
        assert expected_exception_message in result.exception.args[0].message
        assert isinstance(result.exception, ExaConnectionFailedError)
