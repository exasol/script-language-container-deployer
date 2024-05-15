from typing import Callable
from contextlib import ExitStack
from pathlib import Path

import pytest
from _pytest.fixtures import FixtureRequest

from pyexasol import ExaConnection
from pytest_itde import config
from exasol_bucketfs_utils_python.bucketfs_factory import BucketFSFactory

from exasol.python_extension_common.deployment.language_container_deployer import (
    LanguageContainerDeployer, LanguageActivationLevel)

from test.utils.revert_language_settings import revert_language_settings
from test.utils.db_utils import (create_schema, assert_udf_running)


def create_container_deployer(language_alias: str,
                              pyexasol_connection: ExaConnection,
                              bucketfs_config: config.BucketFs) -> LanguageContainerDeployer:
    bucket_fs_factory = BucketFSFactory()
    bucketfs_location = bucket_fs_factory.create_bucketfs_location(
        url=f"{bucketfs_config.url}/default/container;bfsdefault",
        user=f"{bucketfs_config.username}",
        pwd=f"{bucketfs_config.password}",
        base_path=None)
    return LanguageContainerDeployer(
        pyexasol_connection, language_alias, bucketfs_location)


def test_language_container_deployer(
        request: FixtureRequest,
        connection_factory: Callable[[config.Exasol], ExaConnection],
        exasol_config: config.Exasol,
        bucketfs_config: config.BucketFs,
        container_path: str):
    """
    Tests the deployment of a container in one call, including the activation at the System level.
    """
    test_name: str = request.node.name
    schema = test_name
    language_alias = f"PYTHON3_PEC_{test_name.upper()}"
    with ExitStack() as stack:
        pyexasol_connection = stack.enter_context(connection_factory(exasol_config))
        stack.enter_context(revert_language_settings(pyexasol_connection))
        create_schema(pyexasol_connection, schema)
        deployer = create_container_deployer(language_alias=language_alias,
                                             pyexasol_connection=pyexasol_connection,
                                             bucketfs_config=bucketfs_config)
        deployer.run(container_file=Path(container_path), alter_system=True, allow_override=True)
        new_connection = stack.enter_context(connection_factory(exasol_config))
        assert_udf_running(new_connection, language_alias, schema)


def test_language_container_deployer_alter_session(
        request: FixtureRequest,
        connection_factory: Callable[[config.Exasol], ExaConnection],
        exasol_config: config.Exasol,
        bucketfs_config: config.BucketFs,
        container_url: str,
        container_name: str):
    """
    Tests the deployment of a container in two stages - uploading the container
    followed by activation at the Session level.
    """
    test_name: str = request.node.name
    schema = test_name
    language_alias = f"PYTHON3_PEC_{test_name.upper()}"
    with ExitStack() as stack:
        pyexasol_connection = stack.enter_context(connection_factory(exasol_config))
        stack.enter_context(revert_language_settings(pyexasol_connection))
        create_schema(pyexasol_connection, schema)
        deployer = create_container_deployer(language_alias=language_alias,
                                             pyexasol_connection=pyexasol_connection,
                                             bucketfs_config=bucketfs_config)
        deployer.download_and_run(container_url, container_name, alter_system=False)
        new_connection = stack.enter_context(connection_factory(exasol_config))
        deployer = create_container_deployer(language_alias=language_alias,
                                             pyexasol_connection=new_connection,
                                             bucketfs_config=bucketfs_config)
        deployer.activate_container(container_name, LanguageActivationLevel.Session, True)
        assert_udf_running(new_connection, language_alias, schema)


def test_language_container_deployer_activation_fail(
        request: FixtureRequest,
        connection_factory: Callable[[config.Exasol], ExaConnection],
        exasol_config: config.Exasol,
        bucketfs_config: config.BucketFs,
        container_path: str,
        container_name: str):
    """
    Tests that an attempt to activate a container using alias that already exists
    causes an exception if overriding is disallowed.
    """
    test_name: str = request.node.name
    schema = test_name
    language_alias = f"PYTHON3_PEC_{test_name.upper()}"
    with ExitStack() as stack:
        pyexasol_connection = stack.enter_context(connection_factory(exasol_config))
        stack.enter_context(revert_language_settings(pyexasol_connection))
        create_schema(pyexasol_connection, schema)
        deployer = create_container_deployer(language_alias=language_alias,
                                             pyexasol_connection=pyexasol_connection,
                                             bucketfs_config=bucketfs_config)
        deployer.run(container_file=Path(container_path), alter_system=True, allow_override=True)
        new_connection = stack.enter_context(connection_factory(exasol_config))
        deployer = create_container_deployer(language_alias=language_alias,
                                             pyexasol_connection=new_connection,
                                             bucketfs_config=bucketfs_config)
        with pytest.raises(RuntimeError):
            deployer.activate_container(container_name, LanguageActivationLevel.System, False)
