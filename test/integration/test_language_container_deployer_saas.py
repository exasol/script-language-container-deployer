from contextlib import ExitStack
from pathlib import Path
import time

import pytest
from pyexasol import ExaConnection
import exasol.bucketfs as bfs

from exasol.python_extension_common.deployment.language_container_deployer import (
    LanguageContainerDeployer)

from test.utils.revert_language_settings import revert_language_settings
from test.utils.db_utils import (create_schema, assert_udf_running)

TEST_SCHEMA = "PEC_DEPLOYER_TESTS"
TEST_LANGUAGE_ALIAS = "PYTHON3_PEC_TESTS"


def create_container_deployer(language_alias: str,
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


@pytest.mark.saas
def test_dummy_saas_test(
        saas_host,
        saas_token,
        saas_account_id):
    assert saas_host
    assert saas_account_id
    assert saas_token
