from __future__ import annotations
from typing import Any
from contextlib import ExitStack
from pathlib import Path
import time

import pytest
import pyexasol
import exasol.bucketfs as bfs

from exasol.python_extension_common.deployment.language_container_deployer import (
    LanguageContainerDeployer)

from test.utils.revert_language_settings import revert_language_settings
from test.utils.db_utils import (create_schema, assert_udf_running)

TEST_SCHEMA = "PEC_DEPLOYER_TESTS"
TEST_LANGUAGE_ALIAS = "PYTHON3_PEC_TESTS"


def create_container_deployer(language_alias: str,
                              pyexasol_connection: pyexasol.ExaConnection,
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


@pytest.mark.saas
def test_language_container_deployer(
        saas_host: str,
        saas_token: str,
        saas_account_id: str,
        operational_saas_database_id: str,
        saas_connection_params: dict[str, Any],
        container_path: str):
    """
    Tests the deployment of a container in one call, including the activation at the System level.
    """
    with ExitStack() as stack:
        pyexasol_connection = stack.enter_context(pyexasol.connect(**saas_connection_params, compression=True))
        stack.enter_context(revert_language_settings(pyexasol_connection))
        create_schema(pyexasol_connection, TEST_SCHEMA)
        deployer = create_container_deployer(language_alias=TEST_LANGUAGE_ALIAS,
                                             pyexasol_connection=pyexasol_connection,
                                             url=saas_host,
                                             account_id=saas_account_id,
                                             database_id=operational_saas_database_id,
                                             token=saas_token)
        deployer.run(container_file=Path(container_path), alter_system=True, allow_override=True)

        # Need to give the SaaS BucketFS some time to digest the language container.
        # The required time is somewhere between 20 seconds and 5 minutes.
        time.sleep(300.)
        # In order to check that the uploaded container works we need a new pyexasol connection.
        # The system level activation of the language container didn't affect pre-existing sessions.
        new_connection = stack.enter_context(pyexasol.connect(**saas_connection_params, compression=True))
        assert_udf_running(new_connection, TEST_LANGUAGE_ALIAS, TEST_SCHEMA)
