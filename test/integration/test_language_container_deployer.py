from typing import Callable
from contextlib import ExitStack
from pathlib import Path

import pytest

from pyexasol import ExaConnection
from pytest_itde import config
import exasol.bucketfs as bfs

from exasol.python_extension_common.deployment.language_container_deployer import (
    LanguageContainerDeployer, LanguageActivationLevel)

from test.utils.revert_language_settings import revert_language_settings
from test.utils.db_utils import (create_schema, assert_udf_running)

TEST_SCHEMA = "PEC_DEPLOYER_TESTS"
TEST_LANGUAGE_ALIAS = "PYTHON3_PEC_TESTS"


def create_container_deployer(language_alias: str,
                              pyexasol_connection: ExaConnection,
                              bucketfs_config: config.BucketFs) -> LanguageContainerDeployer:

    bucketfs_path = bfs.path.build_path(backend=bfs.path.StorageBackend.onprem,
                                        url=bucketfs_config.url,
                                        username=bucketfs_config.username,
                                        password=bucketfs_config.password,
                                        service_name="bfsdefault",
                                        bucket_name="default",
                                        verify=False,
                                        path="container")
    return LanguageContainerDeployer(
        pyexasol_connection, language_alias, bucketfs_path)


def create_container_deployer_saas(language_alias: str,
                                   pyexasol_connection: ExaConnection,
                                   url: str,
                                   account_id: str,
                                   database_id: str,
                                   token: str) -> LanguageContainerDeployer:

    bucketfs_path = bfs.path.build_path(backend=bfs.path.StorageBackend.saas,
                                        url=url,
                                        account_id=account_id,
                                        database_id=database_id,
                                        pat=token,
                                        path="container")
    return LanguageContainerDeployer(
        pyexasol_connection, language_alias, bucketfs_path)


def test_language_container_deployer(
        itde: config.TestConfig,
        connection_factory: Callable[[config.Exasol], ExaConnection],
        container_path: str):
    """
    Tests the deployment of a container in one call, including the activation at the System level.
    """
    with ExitStack() as stack:
        pyexasol_connection = stack.enter_context(connection_factory(itde.db))
        stack.enter_context(revert_language_settings(pyexasol_connection))
        create_schema(pyexasol_connection, TEST_SCHEMA)
        deployer = create_container_deployer(language_alias=TEST_LANGUAGE_ALIAS,
                                             pyexasol_connection=pyexasol_connection,
                                             bucketfs_config=itde.bucketfs)
        deployer.run(container_file=Path(container_path), alter_system=True, allow_override=True)
        new_connection = stack.enter_context(connection_factory(itde.db))
        assert_udf_running(new_connection, TEST_LANGUAGE_ALIAS, TEST_SCHEMA)


def test_language_container_deployer_saas(
        itde: config.TestConfig,
        connection_factory: Callable[[config.Exasol], ExaConnection],
        container_path: str):
    """
    Tests the deployment of a container in one call, including the activation at the System level.
    """
    with ExitStack() as stack:
        pyexasol_connection = stack.enter_context(connection_factory(itde.db))
        stack.enter_context(revert_language_settings(pyexasol_connection))
        create_schema(pyexasol_connection, TEST_SCHEMA)
        deployer = create_container_deployer(language_alias=TEST_LANGUAGE_ALIAS,
                                             pyexasol_connection=pyexasol_connection,
                                             bucketfs_config=itde.bucketfs)
        deployer.run(container_file=Path(container_path), alter_system=True, allow_override=True)
        new_connection = stack.enter_context(connection_factory(itde.db))
        assert_udf_running(new_connection, TEST_LANGUAGE_ALIAS, TEST_SCHEMA)


def test_language_container_deployer_alter_session(
        itde: config.TestConfig,
        connection_factory: Callable[[config.Exasol], ExaConnection],
        container_url: str,
        container_name: str):
    """
    Tests the deployment of a container in two stages - uploading the container
    followed by activation at the Session level.
    """
    with ExitStack() as stack:
        pyexasol_connection = stack.enter_context(connection_factory(itde.db))
        stack.enter_context(revert_language_settings(pyexasol_connection))
        create_schema(pyexasol_connection, TEST_SCHEMA)
        deployer = create_container_deployer(language_alias=TEST_LANGUAGE_ALIAS,
                                             pyexasol_connection=pyexasol_connection,
                                             bucketfs_config=itde.bucketfs)
        deployer.download_and_run(container_url, container_name, alter_system=False)
        new_connection = stack.enter_context(connection_factory(itde.db))
        deployer = create_container_deployer(language_alias=TEST_LANGUAGE_ALIAS,
                                             pyexasol_connection=new_connection,
                                             bucketfs_config=itde.bucketfs)
        deployer.activate_container(container_name, LanguageActivationLevel.Session, True)
        assert_udf_running(new_connection, TEST_LANGUAGE_ALIAS, TEST_SCHEMA)


def test_language_container_deployer_activation_fail(
        itde: config.TestConfig,
        connection_factory: Callable[[config.Exasol], ExaConnection],
        container_path: str,
        container_name: str):
    """
    Tests that an attempt to activate a container using an alias that already exists
    causes an exception if overriding is disallowed.
    """
    with ExitStack() as stack:
        pyexasol_connection = stack.enter_context(connection_factory(itde.db))
        stack.enter_context(revert_language_settings(pyexasol_connection))
        create_schema(pyexasol_connection, TEST_SCHEMA)
        deployer = create_container_deployer(language_alias=TEST_LANGUAGE_ALIAS,
                                             pyexasol_connection=pyexasol_connection,
                                             bucketfs_config=itde.bucketfs)
        deployer.run(container_file=Path(container_path), alter_system=True, allow_override=True)
        new_connection = stack.enter_context(connection_factory(itde.db))
        deployer = create_container_deployer(language_alias=TEST_LANGUAGE_ALIAS,
                                             pyexasol_connection=new_connection,
                                             bucketfs_config=itde.bucketfs)
        with pytest.raises(RuntimeError):
            deployer.activate_container(container_name, LanguageActivationLevel.System, False)
