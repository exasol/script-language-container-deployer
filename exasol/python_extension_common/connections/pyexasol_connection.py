import pyexasol     # type: ignore
import exasol.saas.client.api_access as saas_api    # type: ignore

from exasol.python_extension_common.deployment.language_container_deployer import get_websocket_sslopt


def open_pyexasol_connection(
        dsn: str | None = None,
        db_user: str | None = None,
        db_pass: str | None = None,
        saas_url: str | None = None,
        saas_account_id: str | None = None,
        saas_database_id: str | None = None,
        saas_database_name: str | None = None,
        saas_token: str | None = None,
        schema: str = '',
        use_ssl_cert_validation: bool = True,
        ssl_trusted_ca: str | None = None,
        ssl_client_certificate: str | None = None,
        ssl_private_key: str | None = None) -> pyexasol.ExaConnection:
    """
    Creates a database connections object, either in an On-Prem or SaaS database,
    depending on the provided parameters.

    Raises a ValueError if the provided parameters are sufficient for neither On-Prem
    nor SaaS connections.

    Parameters:
        dsn                 - On-Prem database host address, including the port
        db_user             - On-Prem database username
        db_pass             - On-Prem database user password
        saas_url            - SaaS service url
        saas_account_id     - SaaS account id
        saas_database_id    - SaaS database id
        saas_database_name  - SaaS database name, to be used in case the id is unknown
        saas_token          - SaaS Personal Access Token (PAT)
        schema              - Schema where the scripts should be created
        use_ssl_cert_validation - Use SSL server certificate validation
        ssl_trusted_ca          - Path to a file or directory with an SSL trusted CA bundle
        ssl_client_certificate  - Path to a file with the SSL client certificate
        ssl_private_key         - Path to a file with the SSL client private key
    """

    # Infer where the database is - On-Prem or SaaS.
    if all((dsn, db_user, db_pass)):
        connection_params = {'dsn': dsn, 'user': db_user, 'password': db_pass}
    elif all((saas_url, saas_account_id, saas_token,
              any((saas_database_id, saas_database_name)))):
        connection_params = saas_api.get_connection_params(host=saas_url,
                                                           account_id=saas_account_id,
                                                           database_id=saas_database_id,
                                                           database_name=saas_database_name,
                                                           pat=saas_token)
    else:
        raise ValueError('Incomplete parameter list. '
                         'Please either provide the parameters [dns, db_user, db_pass] '
                         'for an On-Prem database or [saas_url, saas_account_id, '
                         'saas_database_id or saas_database_name, saas_token] '
                         'for a SaaS database.')

    websocket_sslopt = get_websocket_sslopt(use_ssl_cert_validation, ssl_trusted_ca,
                                            ssl_client_certificate, ssl_private_key)

    return pyexasol.connect(**connection_params, schema=schema,
                            encryption=True,
                            websocket_sslopt=websocket_sslopt,
                            compression=True)
