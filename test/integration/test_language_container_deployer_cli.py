from typing import Optional, Callable
from contextlib import ExitStack
from pathlib import Path

from urllib.parse import urlparse
from _pytest.fixtures import FixtureRequest
from click.testing import CliRunner
from pyexasol import ExaConnection, ExaConnectionFailedError
from pytest_itde import config

from test.utils.revert_language_settings import revert_language_settings
from test.utils.db_utils import (create_schema, assert_udf_running)


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
        request: FixtureRequest,
        connection_factory: Callable[[config.Exasol], ExaConnection],
        exasol_config: config.Exasol,
        bucketfs_config: config.BucketFs,
        container_path: str,
        main_func
):
    test_name: str = request.node.name
    schema = test_name
    language_alias = f"PYTHON3_TE_{test_name.upper()}"
    with ExitStack() as stack:
        pyexasol_connection = stack.enter_context(connection_factory(exasol_config))
        stack.enter_context(revert_language_settings(pyexasol_connection))
        create_schema(pyexasol_connection, schema)
        result = call_language_definition_deployer_cli(main_func,
                                                       container_path=container_path,
                                                       language_alias=language_alias,
                                                       exasol_config=exasol_config,
                                                       bucketfs_config=bucketfs_config)
        assert result.exit_code == 0
        assert result.exception is None
        assert result.stdout == ""
        new_connection = stack.enter_context(connection_factory(exasol_config))
        assert_udf_running(new_connection, language_alias, schema)


def test_language_container_deployer_cli_by_downloading_container(
        request: FixtureRequest,
        connection_factory: Callable[[config.Exasol], ExaConnection],
        exasol_config: config.Exasol,
        bucketfs_config: config.BucketFs,
        container_version,
        main_func
):
    test_name: str = request.node.name
    schema = test_name
    language_alias = f"PYTHON3_TE_{test_name.upper()}"
    with ExitStack() as stack:
        pyexasol_connection = stack.enter_context(connection_factory(exasol_config))
        stack.enter_context(revert_language_settings(pyexasol_connection))
        create_schema(pyexasol_connection, schema)
        result = call_language_definition_deployer_cli(main_func,
                                                       version=container_version,
                                                       language_alias=language_alias,
                                                       exasol_config=exasol_config,
                                                       bucketfs_config=bucketfs_config)
        assert result.exit_code == 0
        assert result.exception is None
        assert result.stdout == ""
        new_connection = stack.enter_context(connection_factory(exasol_config))
        assert_udf_running(new_connection, language_alias, schema)


def test_language_container_deployer_cli_with_missing_container_option(
        request: FixtureRequest,
        connection_factory: Callable[[config.Exasol], ExaConnection],
        exasol_config: config.Exasol,
        bucketfs_config: config.BucketFs,
        main_func
):
    test_name: str = request.node.name
    language_alias = f"PYTHON3_PEC_{test_name.upper()}"
    with ExitStack() as stack:
        pyexasol_connection = stack.enter_context(connection_factory(exasol_config))
        stack.enter_context(revert_language_settings(pyexasol_connection))
        result = call_language_definition_deployer_cli(main_func,
                                                       language_alias=language_alias,
                                                       bucketfs_config=bucketfs_config,
                                                       exasol_config=exasol_config)
        assert result.exit_code == 1
        assert isinstance(result.exception, ValueError)


def test_language_container_deployer_cli_with_check_cert(
        request: FixtureRequest,
        connection_factory: Callable[[config.Exasol], ExaConnection],
        exasol_config: config.Exasol,
        bucketfs_config: config.BucketFs,
        container_path: str,
        main_func
):
    expected_exception_message = '[SSL: CERTIFICATE_VERIFY_FAILED]'
    test_name: str = request.node.name
    schema = test_name
    language_alias = f"PYTHON3_TE_{test_name.upper()}"
    with ExitStack() as stack:
        pyexasol_connection = stack.enter_context(connection_factory(exasol_config))
        stack.enter_context(revert_language_settings(pyexasol_connection))
        create_schema(pyexasol_connection, schema)
        result = call_language_definition_deployer_cli(main_func,
                                                       container_path=container_path,
                                                       language_alias=language_alias,
                                                       exasol_config=exasol_config,
                                                       bucketfs_config=bucketfs_config,
                                                       use_ssl_cert_validation=True)
        assert result.exit_code == 1
        assert expected_exception_message in result.exception.args[0].message
        assert isinstance(result.exception, ExaConnectionFailedError)
