from __future__ import annotations
from typing import Any
import os
import pytest
import click
import requests

from exasol.saas.client.api_access import get_connection_params

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


@pytest.fixture(scope="session")
def saas_connection_params(saas_host, saas_pat, saas_account_id, operational_saas_database_id) -> dict[str, Any]:
    connection_params = get_connection_params(
        host=saas_host,
        account_id=saas_account_id,
        database_id=operational_saas_database_id,
        pat=saas_pat,
    )
    yield connection_params
