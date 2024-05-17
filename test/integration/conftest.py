import os
import pytest
import click
import requests

import pyexasol
from exasol.saas.client.api_access import (
    create_saas_client,
    timestamp_name,
    OpenApiAccess,
)
from exasol.saas.client.openapi.models import CreateAllowedIP
from exasol.saas.client.openapi.api.security.add_allowed_ip import sync as add_allowed_ip
from exasol.saas.client.openapi.api.clusters.list_clusters import sync as list_clusters
from exasol.saas.client.openapi.api.clusters.get_cluster_connection import sync as get_cluster_connection

from exasol.python_extension_common.deployment.language_container_deployer_cli import (
    language_container_deployer_main, slc_parameter_formatters, CustomizableParameters)


SLC_NAME = "template-Exasol-all-python-3.10_release.tar.gz"

SLC_URL_FORMATTER = ("https://github.com/exasol/script-languages-release/releases/"
                     "download/{version}/") + SLC_NAME

VERSION = "8.0.0"


@pytest.fixture
def main_func():

    @click.group()
    def fake_main():
        pass

    slc_parameter_formatters.set_formatter(CustomizableParameters.container_url, SLC_URL_FORMATTER)
    slc_parameter_formatters.set_formatter(CustomizableParameters.container_name, SLC_NAME)

    fake_main.add_command(language_container_deployer_main)
    return fake_main


@pytest.fixture(scope='session')
def container_version() -> str:
    return VERSION


@pytest.fixture(scope='session')
def container_name() -> str:
    return SLC_NAME


@pytest.fixture(scope='session')
def container_url(container_version) -> str:
    return SLC_URL_FORMATTER.format(version=VERSION)


@pytest.fixture(scope='session')
def container_path(tmpdir_factory, container_url, container_name) -> str:

    response = requests.get(container_url, allow_redirects=True)
    response.raise_for_status()
    slc_path = tmpdir_factory.mktemp('container').join(container_name)
    slc_path = str(slc_path)
    with open(slc_path, 'wb') as f:
        f.write(response.content)
    return slc_path


def _env(var: str) -> str:
    result = os.environ.get(var)
    if result:
        return result
    raise RuntimeError(f"Environment variable {var} is empty.")


@pytest.fixture(scope="session")
def saas_host() -> str:
    return _env("SAAS_HOST")


@pytest.fixture(scope="session")
def saas_token() -> str:
    return _env("SAAS_PAT")


@pytest.fixture(scope="session")
def saas_account_id() -> str:
    return _env("SAAS_ACCOUNT_ID")


@pytest.fixture(scope="session")
def api_access(saas_host, saas_token, saas_account_id) -> OpenApiAccess:
    with create_saas_client(saas_host, saas_token) as client:
        yield OpenApiAccess(client, saas_account_id)


@pytest.fixture(scope="session")
def operational_saas_database_id(api_access) -> str:
    database_name = timestamp_name('PEC')
    with api_access.database(database_name) as db:
        api_access.wait_until_running(db.id)
        yield db.id


@pytest.fixture(scope="session")
def saas_connection_factory(saas_host, saas_token, saas_account_id, operational_saas_database_id):

    with create_saas_client(saas_host, saas_token) as client:
        ip_rule = CreateAllowedIP(name=timestamp_name('PEC_IP'),
                                  cidr_ip='0.0.0.0/0')
        add_allowed_ip(saas_account_id,
                       client=client,
                       body=ip_rule)
        clusters = list_clusters(saas_account_id,
                                 operational_saas_database_id,
                                 client=client)
        cluster_id = next(filter(lambda cl: cl.main_cluster, clusters)).id
        connections = get_cluster_connection(saas_account_id,
                                             operational_saas_database_id,
                                             cluster_id,
                                             client=client)

        def create_pyexasol_connection(**kwargs) -> pyexasol.ExaConnection:
            return pyexasol.connect(dsn=f'{connections.dns}:{connections.port}',
                                    user=connections.db_username,
                                    password=saas_token,
                                    **kwargs)
        yield create_pyexasol_connection
