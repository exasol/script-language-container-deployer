from typing import Optional, Any
import os
import re
from enum import Enum
from pathlib import Path
import click
from exasol.python_extension_common.deployment.language_container_deployer import LanguageContainerDeployer


class CustomizableParameters(Enum):
    """
    Parameters of the cli that can be programmatically customised by a developer
    of a specialised version of the cli.
    The names in the enum list should match the parameter names in language_container_deployer_main.
    """
    container_url = 1
    container_name = 2


class _ParameterFormatters:
    """
    Class facilitating customization of the cli.

    The idea is that some of the cli parameters can be programmatically customized based
    on values of other parameters and externally supplied formatters. For example a specialized
    version of the cli may want to provide its own url. Furthermore, this url will depend on
    the user supplied parameter called "version". The solution is to set a formatter for the
    url, for instance "http://my_stuff/{version}/my_data". If the user specifies non-empty version
    parameter the url will be fully formed.

    A formatter may include more than one parameter. In the previous example the url could,
    for instance, also include a username: "http://my_stuff/{version}/{user}/my_data".

    Note that customized parameters can only be updated in a callback function. There is no
    way to inject them directly into the cli. Also, the current implementation doesn't perform
    the update if the value of the parameter dressed with the callback is None.

    IMPORTANT! Please make sure that the formatters are set up before the call to the cli function,
    e.g. language_container_deployer_main, is executed.
    """
    def __init__(self):
        self._formatters = {}

    def __call__(self, ctx: click.Context, param: click.Parameter, value: Optional[Any]) -> Optional[Any]:

        def update_parameter(parameter_name: str, formatter: str) -> None:
            param_formatter = ctx.params.get(parameter_name, formatter)
            if param_formatter:
                # Enclose in double curly brackets all other parameters in the formatting string,
                # to avoid the missing parameters' error. Below is an example of a formatter string
                # before and after applying the regex, assuming the current parameter is 'version'.
                # 'something-with-{version}/tailored-for-{user}' => 'something-with-{version}/tailored-for-{{user}}'
                # We were looking for all occurrences of a pattern '{some_name}', where some_name is not version.
                pattern = r'\{(?!' + (param.name or '') + r'\})\w+\}'
                param_formatter = re.sub(pattern, lambda m: f'{{{m.group(0)}}}', param_formatter)
                kwargs = {param.name: value}
                ctx.params[parameter_name] = param_formatter.format(**kwargs)

        if value is not None:
            for prm_name, prm_formatter in self._formatters.items():
                update_parameter(prm_name, prm_formatter)

        return value

    def set_formatter(self, custom_parameter: CustomizableParameters, formatter: str) -> None:
        """ Sets a formatter for a customizable parameter. """
        self._formatters[custom_parameter.name] = formatter

    def clear_formatters(self):
        """ Deletes all formatters, mainly for testing purposes. """
        self._formatters.clear()


# Global cli customization object.
# Specialized versions of this cli should use this object to set custom parameter formatters.
slc_parameter_formatters = _ParameterFormatters()


# This text will be displayed instead of the actual value, if found in an environment
# variable, in a prompt.
SECRET_DISPLAY = '***'


class SecretParams(Enum):
    """
    This enum serves as a definition of confidential parameters which values should not be
    displayed in the console, unless the user types them in the command line.

    The enum name is also the name of the environment variable where the correspondent
    secret value can be stored.

    The enum value is also the name of the cli parameter.
    """
    DB_PASSWORD = 'db-pass'
    BUCKETFS_PASSWORD = 'bucketfs-password'
    SAAS_ACCOUNT_ID = 'saas-account-id'
    SAAS_DATABASE_ID = 'saas-database-id'
    SAAS_TOKEN = 'saas-token'


def secret_callback(ctx: click.Context, param: click.Option, value: Any):
    """
    Here we try to get the secret parameter value from an environment variable.
    The reason for doing this in the callback instead of using a callable default is
    that we don't want the default to be displayed in the prompt. There seems to
    be no way of altering this behaviour.
    """
    if value == SECRET_DISPLAY:
        secret_param = SecretParams(param.opts[0][2:])
        return os.environ.get(secret_param.name)
    return value


@click.command(name="language-container")
@click.option('--bucketfs-name', type=str)
@click.option('--bucketfs-host', type=str)
@click.option('--bucketfs-port', type=int)
@click.option('--bucketfs-use-https', type=bool, default=False)
@click.option('--bucketfs-user', type=str)
@click.option(f'--{SecretParams.BUCKETFS_PASSWORD.value}', type=str,
              prompt='BucketFS password', prompt_required=False,
              hide_input=True, default=SECRET_DISPLAY, callback=secret_callback)
@click.option('--bucket', type=str)
@click.option('--saas-url', type=str,
              default='https://cloud.exasol.com')
@click.option(f'--{SecretParams.SAAS_ACCOUNT_ID.value}', type=str,
              prompt='SaaS account id', prompt_required=False,
              hide_input=True, default=SECRET_DISPLAY, callback=secret_callback)
@click.option(f'--{SecretParams.SAAS_DATABASE_ID.value}', type=str,
              prompt='SaaS database id', prompt_required=False,
              hide_input=True, default=SECRET_DISPLAY, callback=secret_callback)
@click.option('--saas-database-name', type=str)
@click.option(f'--{SecretParams.SAAS_TOKEN.value}', type=str,
              prompt='SaaS token', prompt_required=False,
              hide_input=True, default=SECRET_DISPLAY, callback=secret_callback)
@click.option('--path-in-bucket', type=str)
@click.option('--container-file',
              type=click.Path(exists=True, file_okay=True))
@click.option('--version', type=str, expose_value=False,
              callback=slc_parameter_formatters)
@click.option('--dsn', type=str)
@click.option('--db-user', type=str)
@click.option(f'--{SecretParams.DB_PASSWORD.value}', type=str,
              prompt='DB password', prompt_required=False,
              hide_input=True, default=SECRET_DISPLAY, callback=secret_callback)
@click.option('--language-alias', type=str, default="PYTHON3_EXT")
@click.option('--ssl-cert-path', type=str, default="")
@click.option('--ssl-client-cert-path', type=str, default="")
@click.option('--ssl-client-private-key', type=str, default="")
@click.option('--use-ssl-cert-validation/--no-use-ssl-cert-validation', type=bool, default=True)
@click.option('--upload-container/--no-upload_container', type=bool, default=True)
@click.option('--alter-system/--no-alter-system', type=bool, default=True)
@click.option('--allow-override/--disallow-override', type=bool, default=False)
@click.option('--wait_for_completion/--no-wait_for_completion', type=bool, default=True)
def language_container_deployer_main(
        bucketfs_name: str,
        bucketfs_host: str,
        bucketfs_port: int,
        bucketfs_use_https: bool,
        bucketfs_user: str,
        bucketfs_password: str,
        bucket: str,
        saas_url: str,
        saas_account_id: str,
        saas_database_id: str,
        saas_database_name: str,
        saas_token: str,
        path_in_bucket: str,
        container_file: str,
        dsn: str,
        db_user: str,
        db_pass: str,
        language_alias: str,
        ssl_cert_path: str,
        ssl_client_cert_path: str,
        ssl_client_private_key: str,
        use_ssl_cert_validation: bool,
        upload_container: bool,
        alter_system: bool,
        allow_override: bool,
        wait_for_completion: bool,
        container_url: Optional[str] = None,
        container_name: Optional[str] = None):

    deployer = LanguageContainerDeployer.create(
        bucketfs_name=bucketfs_name,
        bucketfs_host=bucketfs_host,
        bucketfs_port=bucketfs_port,
        bucketfs_use_https=bucketfs_use_https,
        bucketfs_user=bucketfs_user,
        bucketfs_password=bucketfs_password,
        bucket=bucket,
        saas_url=saas_url,
        saas_account_id=saas_account_id,
        saas_database_id=saas_database_id,
        saas_database_name=saas_database_name,
        saas_token=saas_token,
        path_in_bucket=path_in_bucket,
        dsn=dsn,
        db_user=db_user,
        db_password=db_pass,
        language_alias=language_alias,
        ssl_trusted_ca=ssl_cert_path,
        ssl_client_certificate=ssl_client_cert_path,
        ssl_private_key=ssl_client_private_key,
        use_ssl_cert_validation=use_ssl_cert_validation)

    if not upload_container:
        deployer.run(alter_system=alter_system, allow_override=allow_override,
                     wait_for_completion=wait_for_completion)
    elif container_file:
        deployer.run(container_file=Path(container_file), alter_system=alter_system,
                     allow_override=allow_override, wait_for_completion=wait_for_completion)
    elif container_url and container_name:
        deployer.download_and_run(container_url, container_name, alter_system=alter_system,
                                  allow_override=allow_override, wait_for_completion=wait_for_completion)
    else:
        # The error message should mention the parameters which the callback is specified for being missed.
        raise ValueError("To upload a language container you should specify either its "
                         "release version or a path of the already downloaded container file.")
