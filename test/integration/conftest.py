from pathlib import Path

import pytest
import click
import requests

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
def container_path(tmp_path: Path, container_url) -> Path:

    slc_path = tmp_path / SLC_NAME
    response = requests.get(container_url)
    response.raise_for_status()
    with slc_path.open('wb') as f:
        f.write(response.content)
    return slc_path
