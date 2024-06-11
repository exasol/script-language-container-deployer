from enum import Enum
from textwrap import dedent
from typing import List, Optional, Dict
from pathlib import Path, PurePosixPath
import logging
import tempfile
import ssl
import requests     # type: ignore
import pyexasol     # type: ignore
import exasol.bucketfs as bfs   # type: ignore
from exasol.saas.client.api_access import (get_connection_params, get_database_id)      # type: ignore

from exasol.python_extension_common.deployment.language_container_validator import (
    wait_language_container, temp_schema
)


logger = logging.getLogger(__name__)


def get_websocket_sslopt(use_ssl_cert_validation: bool = True,
                         ssl_trusted_ca: Optional[str] = None,
                         ssl_client_certificate: Optional[str] = None,
                         ssl_private_key: Optional[str] = None) -> dict:
    """
    Returns a dictionary in the winsocket-client format
    (see https://websocket-client.readthedocs.io/en/latest/faq.html#what-else-can-i-do-with-sslopts)
    """

    # Is server certificate validation required?
    sslopt: Dict[str, object] = {"cert_reqs": ssl.CERT_REQUIRED if use_ssl_cert_validation else ssl.CERT_NONE}

    # Is a bundle with trusted CAs provided?
    if ssl_trusted_ca:
        trusted_ca_path = Path(ssl_trusted_ca)
        if trusted_ca_path.is_dir():
            sslopt["ca_cert_path"] = ssl_trusted_ca
        elif trusted_ca_path.is_file():
            sslopt["ca_certs"] = ssl_trusted_ca
        else:
            raise ValueError(f"Trusted CA location {ssl_trusted_ca} doesn't exist.")

    # Is client's own certificate provided?
    if ssl_client_certificate:
        if not Path(ssl_client_certificate).is_file():
            raise ValueError(f"Certificate file {ssl_client_certificate} doesn't exist.")
        sslopt["certfile"] = ssl_client_certificate
        if ssl_private_key:
            if not Path(ssl_private_key).is_file():
                raise ValueError(f"Private key file {ssl_private_key} doesn't exist.")
            sslopt["keyfile"] = ssl_private_key

    return sslopt


class LanguageActivationLevel(Enum):
    """
    Language activation level, i.e.
    ALTER <LanguageActivationLevel> SET SCRIPT_LANGUAGES=...
    """
    Session = 'SESSION'
    System = 'SYSTEM'


def get_language_settings(pyexasol_conn: pyexasol.ExaConnection, alter_type: LanguageActivationLevel) -> str:
    """
    Reads the current language settings at the specified level.

    pyexasol_conn    - Opened database connection.
    alter_type       - Activation level - SYSTEM or SESSION.
    """
    result = pyexasol_conn.execute(
        f"""SELECT "{alter_type.value}_VALUE" FROM SYS.EXA_PARAMETERS WHERE
        PARAMETER_NAME='SCRIPT_LANGUAGES'""").fetchall()
    return result[0][0]


def get_udf_path(bucket_base_path: bfs.path.PathLike, bucket_file: str) -> PurePosixPath:
    """
    Returns the path of the specified file in a bucket, as it's seen from a UDF

    bucket_base_path    - Base directory in the bucket
    bucket_file         - File path in the bucket, relative to the base directory.
    """

    file_path = bucket_base_path / bucket_file
    return PurePosixPath(file_path.as_udf_path())


class LanguageContainerDeployer:

    def __init__(self,
                 pyexasol_connection: pyexasol.ExaConnection,
                 language_alias: str,
                 bucketfs_path: bfs.path.PathLike) -> None:

        self._bucketfs_path = bucketfs_path
        self._language_alias = language_alias
        self._pyexasol_conn = pyexasol_connection
        logger.debug("Init %s", LanguageContainerDeployer.__name__)

    def download_and_run(self, url: str,
                         bucket_file_path: str,
                         alter_system: bool = True,
                         allow_override: bool = False,
                         wait_for_completion: bool = True) -> None:
        """
        Downloads the language container from the provided url to a temporary file and then deploys it.
        See docstring on the `run` method for details on what is involved in the deployment.

        url              - Address where the container will be downloaded from.
        bucket_file_path - Path within the designated bucket where the container should be uploaded.
        alter_system     - If True will try to activate the container at the System level.
        allow_override   - If True the activation of a language container with the same alias will be
                           overriden, otherwise a RuntimeException will be thrown.
        wait_for_completion - If True will wait until the language container becomes operational.
        """

        with tempfile.NamedTemporaryFile() as tmp_file:
            response = requests.get(url, stream=True, timeout=300)
            response.raise_for_status()
            tmp_file.write(response.content)

            self.run(Path(tmp_file.name), bucket_file_path, alter_system, allow_override,
                     wait_for_completion)

    def run(self, container_file: Optional[Path] = None,
            bucket_file_path: Optional[str] = None,
            alter_system: bool = True,
            allow_override: bool = False,
            wait_for_completion: bool = True) -> None:
        """
        Deploys the language container. This includes two steps, both of which are optional:
        - Uploading the container into the database. This step can be skipped if the container
          has already been uploaded.
        - Activating the container. In case the container does not get activated at the System
        level, two alternative activation SQL commands (one for the System and one for the Session
        levels) will be printed on the console.

        container_file   - Path of the container tar.gz file in a local file system.
                           If not provided the container is assumed to be uploaded already.
        bucket_file_path - Path within the designated bucket where the container should be uploaded.
                           If not specified the name of the container file will be used instead.
        alter_system     - If True will try to activate the container at the System level.
        allow_override   - If True the activation of a language container with the same alias will be
                           overriden, otherwise a RuntimeException will be thrown.
        wait_for_completion - If True will wait until the language container becomes operational.
        """

        if not bucket_file_path:
            if not container_file:
                raise ValueError('Either a container file or a bucket file path must be specified.')
            bucket_file_path = container_file.name

        if container_file:
            self.upload_container(container_file, bucket_file_path)

        # Activate the language container.
        if alter_system:
            self.activate_container(bucket_file_path, LanguageActivationLevel.System,
                                    allow_override)
        self.activate_container(bucket_file_path, LanguageActivationLevel.Session,
                                allow_override)

        # Maybe wait until the container becomes operational.
        if container_file and wait_for_completion:
            with temp_schema(self._pyexasol_conn) as schema:
                wait_language_container(self._pyexasol_conn, self._language_alias, schema)

        if not alter_system:
            message = dedent(f"""
            In SQL, you can activate the SLC
            by using the following statements:

            To activate the SLC only for the current session:
            {self.generate_activation_command(bucket_file_path, LanguageActivationLevel.Session, True)}

            To activate the SLC on the system:
            {self.generate_activation_command(bucket_file_path, LanguageActivationLevel.System, True)}
            """)
            print(message)

    def upload_container(self, container_file: Path,
                         bucket_file_path: Optional[str] = None) -> None:
        """
        Upload the language container to the BucketFS.

        container_file   - Path of the container tar.gz file in a local file system.
        bucket_file_path - Path within the designated bucket where the container should be uploaded.
        """
        if not container_file.is_file():
            raise RuntimeError(f"Container file {container_file} "
                               f"is not a file.")
        with open(container_file, "br") as f:
            file_path = self._bucketfs_path / bucket_file_path
            file_path.write(f)
        logging.debug("Container is uploaded to bucketfs")

    def activate_container(self, bucket_file_path: str,
                           alter_type: LanguageActivationLevel = LanguageActivationLevel.Session,
                           allow_override: bool = False) -> None:
        """
        Activates the language container at the required level.

        bucket_file_path - Path within the designated bucket where the container is uploaded.
        alter_type       - Language activation level, defaults to the SESSION.
        allow_override   - If True the activation of a language container with the same alias will be overriden,
                           otherwise a RuntimeException will be thrown.
        """
        alter_command = self.generate_activation_command(bucket_file_path, alter_type, allow_override)
        self._pyexasol_conn.execute(alter_command)
        logging.debug(alter_command)

    def generate_activation_command(self, bucket_file_path: str,
                                    alter_type: LanguageActivationLevel,
                                    allow_override: bool = False) -> str:
        """
        Generates an SQL command to activate the SLC container at the required level. The command will
        preserve existing activations of other containers identified by different language aliases.
        Activation of a container with the same alias, if exists, will be overwritten.

        bucket_file_path - Path within the designated bucket where the container is uploaded.
        alter_type       - Activation level - SYSTEM or SESSION.
        allow_override   - If True the activation of a language container with the same alias will be overriden,
                           otherwise a RuntimeException will be thrown.
        """
        path_in_udf = get_udf_path(self._bucketfs_path, bucket_file_path)
        new_settings = \
            self._update_previous_language_settings(alter_type, allow_override, path_in_udf)
        alter_command = \
            f"ALTER {alter_type.value} SET SCRIPT_LANGUAGES='{new_settings}';"
        return alter_command

    def _update_previous_language_settings(self, alter_type: LanguageActivationLevel,
                                           allow_override: bool,
                                           path_in_udf: PurePosixPath) -> str:
        prev_lang_settings = get_language_settings(self._pyexasol_conn, alter_type)
        prev_lang_aliases = prev_lang_settings.split(" ")
        self._check_if_requested_language_alias_already_exists(
            allow_override, prev_lang_aliases)
        new_definitions_str = self._generate_new_language_settings(
            path_in_udf, prev_lang_aliases)
        return new_definitions_str

    def get_language_definition(self, bucket_file_path: str):
        """
        Generate a language definition (ALIAS=URL) for the specified bucket file path.

        bucket_file_path - Path within the designated bucket where the container is uploaded.
        """
        path_in_udf = get_udf_path(self._bucketfs_path, bucket_file_path)
        result = self._generate_new_language_settings(path_in_udf=path_in_udf, prev_lang_aliases=[])
        return result

    def _generate_new_language_settings(self, path_in_udf: PurePosixPath,
                                        prev_lang_aliases: List[str]) -> str:
        other_definitions = [
            alias_definition for alias_definition in prev_lang_aliases
            if not alias_definition.startswith(self._language_alias + "=")]
        path_in_udf_without_buckets = PurePosixPath(*path_in_udf.parts[2:])
        new_language_alias_definition = \
            f"{self._language_alias}=localzmq+protobuf:///" \
            f"{path_in_udf_without_buckets}?lang=python#" \
            f"{path_in_udf}/exaudf/exaudfclient_py3"
        new_definitions = other_definitions + [new_language_alias_definition]
        new_definitions_str = " ".join(new_definitions)
        return new_definitions_str

    def _check_if_requested_language_alias_already_exists(
            self, allow_override: bool,
            prev_lang_aliases: List[str]) -> None:
        definition_for_requested_alias = [
            alias_definition for alias_definition in prev_lang_aliases
            if alias_definition.startswith(self._language_alias + "=")]
        if not len(definition_for_requested_alias) == 0:
            warning_message = f"The requested language alias {self._language_alias} is already in use."
            if allow_override:
                logging.warning(warning_message)
            else:
                raise RuntimeError(warning_message)

    @classmethod
    def create(cls,
               language_alias: str, dsn: Optional[str] = None,
               db_user: Optional[str] = None, db_password: Optional[str] = None,
               bucketfs_host: Optional[str] = None, bucketfs_port: Optional[int] = None,
               bucketfs_name: Optional[str] = None, bucket: Optional[str] = None,
               bucketfs_user: Optional[str] = None, bucketfs_password: Optional[str] = None,
               bucketfs_use_https: bool = True,
               saas_url: Optional[str] = None,
               saas_account_id: Optional[str] = None, saas_database_id: Optional[str] = None,
               saas_database_name: Optional[str] = None, saas_token: Optional[str] = None,
               path_in_bucket: str = '',
               use_ssl_cert_validation: bool = True, ssl_trusted_ca: Optional[str] = None,
               ssl_client_certificate: Optional[str] = None,
               ssl_private_key: Optional[str] = None) -> "LanguageContainerDeployer":

        # Infer where the database is - on-prem or SaaS.
        if all((dsn, db_user, db_password, bucketfs_host, bucketfs_port,
                bucketfs_name, bucket, bucketfs_user, bucketfs_password)):
            connection_params = {'dsn': dsn, 'user': db_user, 'password': db_password}
            bfs_url = (f"{'https' if bucketfs_use_https else 'http'}://"
                       f"{bucketfs_host}:{bucketfs_port}")
            verify = ssl_trusted_ca or use_ssl_cert_validation
            bucketfs_path = bfs.path.build_path(backend=bfs.path.StorageBackend.onprem,
                                                url=bfs_url,
                                                username=bucketfs_user,
                                                password=bucketfs_password,
                                                service_name=bucketfs_name,
                                                bucket_name=bucket,
                                                verify=verify,
                                                path=path_in_bucket)

        elif all((saas_url, saas_account_id, saas_token,
                  any((saas_database_id, saas_database_name)))):
            connection_params = get_connection_params(host=saas_url,
                                                      account_id=saas_account_id,
                                                      database_id=saas_database_id,
                                                      database_name=saas_database_name,
                                                      pat=saas_token)
            saas_database_id = (saas_database_id or
                                get_database_id(
                                    host=saas_url,
                                    account_id=saas_account_id,
                                    pat=saas_token,
                                    database_name=saas_database_name
                                ))
            bucketfs_path = bfs.path.build_path(backend=bfs.path.StorageBackend.saas,
                                                url=saas_url,
                                                account_id=saas_account_id,
                                                database_id=saas_database_id,
                                                pat=saas_token,
                                                path=path_in_bucket)
        else:
            raise ValueError('Incomplete parameter list. '
                             'Please either provide the parameters [dns, db_user, '
                             'db_password, bucketfs_host, bucketfs_port, bucketfs_name, '
                             'bucket, bucketfs_user, bucketfs_password] for an On-Prem '
                             'database or [saas_url, saas_account_id, saas_database_id, '
                             'saas_token] for a SaaS database.')

        websocket_sslopt = get_websocket_sslopt(use_ssl_cert_validation, ssl_trusted_ca,
                                                ssl_client_certificate, ssl_private_key)

        pyexasol_conn = pyexasol.connect(**connection_params,
                                         encryption=True,
                                         websocket_sslopt=websocket_sslopt)

        return cls(pyexasol_conn, language_alias, bucketfs_path)
