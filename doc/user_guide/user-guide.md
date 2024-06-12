# Python Extension Common User Guide

## Language Container Deployer

An extension would typically use UDF scripts to enable certain custom functionality within a database.
In most cases, UDF scripts must be backed by a Language Container, that should be installed in the Exasol Database.
A Script Language Container is a mechanism that allows the installation of the chosen programming language and
necessary dependencies in the Exasol Database.

The language container for a particular Extension gets downloaded and installed by executing a deployment script
similar to the one below.

  ```buildoutcfg
  python -m an_exasol_extension.deploy language-container <options>
  ```

The name of the script (```an_exasol_extension.deploy``` in the above command) can vary from one extension to another.
Please check the user guide of a particular extension. The rest of the command line will have a common format. It
will include the command - ```language-container``` - and selected options. The choice of options is primarily
determined by the storage backend being used - On-Prem or SaaS.

### List of options

The table below lists all available options. It shows which ones are applicable for On-Prem and for SaaS backends.
Unless stated otherwise in the comments column, an option is required for either or both backends.

Some of the values, like passwords, are considered confidential. For security reasons, it is recommended to store
those values in environment variables instead of providing them in the command line. The names of the environment
variables are given in the comments column, where applicable. Alternatively, it is possible to put just the name of
an option in the command line, without providing its value. In this case, the command will prompt to enter the value
interactively. For long values, such as the SaaS account id, it is more practical to copy/paste the value from
another source.

| Option name                  | On-Prem | SaaS | Comment                                           |
|:-----------------------------|:-------:|:----:|:--------------------------------------------------|
| dsn                          |   [x]   |      | i.e. <db_host:db_port>                            |
| db-user                      |   [x]   |      |                                                   |
| db-pass                      |   [x]   |      | Env. [DB_PASSWORD]                                |
| bucketfs-name                |   [x]   |      |                                                   |
| bucketfs-host                |   [x]   |      |                                                   |
| bucketfs-port                |   [x]   |      |                                                   |
| bucketfs-user                |   [x]   |      |                                                   |
| bucketfs-password            |   [x]   |      | Env. [BUCKETFS_PASSWORD]                          |
| bucketfs-use-https           |   [x]   |      | Optional boolean, defaults to False               |
| bucket                       |   [x]   |      |                                                   |
| saas-url                     |         | [x]  |                                                   |
| saas-account-id              |         | [x]  | Env. [SAAS_ACCOUNT_ID]                            |
| saas-database-id             |         | [x]  | Optional, Env. [SAAS_DATABASE_ID]                 |
| saas-database-name           |         | [x]  | Optional, provide if the database_id is unknown   |
| saas-token                   |         | [x]  | Env. [SAAS_TOKEN]                                 |
| path-in-bucket               |   [x]   | [x]  |                                                   |
| language-alias               |   [x]   | [x]  |                                                   |
| version                      |   [x]   | [x]  | Optional, provide for downloading SLC from GitHub |
| container-file               |   [x]   | [x]  | Optional, provide for uploading SLC file          |
| ssl-cert-path                |   [x]   | [x]  | Optional                                          |
| [no_]use-ssl-cert-validation |   [x]   | [x]  | Optional boolean, defaults to True                |
| ssl-client-cert-path         |   [x]   |      | Optional                                          |
| ssl-client-private-key       |   [x]   |      | Optional                                          |
| [no_]upload-container        |   [x]   | [x]  | Optional boolean, defaults to True                |
| [no_]alter-system            |   [x]   | [x]  | Optional boolean, defaults to True                |
| [dis]allow-override          |   [x]   | [x]  | Optional boolean, defaults to False               |
| [no_]wait_for_completion     |   [x]   | [x]  | Optional boolean, defaults to True                |

### Container selection

A language container can be deployed in two ways.

* By telling the script to download a particular version of the container from GitHub,
  using the `--version` option. The available versions can be found at the extension's releases page on GitHub.
* By providing a path to the container's archive (*.tar.gz) stored in a local file system,
  using the `--container-file` option. The container can be downloaded from GitHub before
  executing the deployment script.

### TLS/SSL options

The `--ssl-cert-path` is needed if the TLS/SSL certificate is not in the OS truststore.
Generally speaking, this certificate is a list of trusted CA. It is needed for the server's certificate
validation by the client.
The option `--use-ssl-cert-validation`is the default, it can be disabled with `--no-use-ssl-cert-validation`.
One needs to exercise caution when turning the certificate validation off as it potentially lowers the security of the
Database connection.
The "server" certificate described above shall not be confused with the client's own certificate.
In some cases, this certificate may be requested by a server. The client certificate may or may not include
the private key. In the latter case, the key may be provided as a separate file.

### Language container activation

By default, the deployment command will upload and activate the language container at the System level.
The latter requires the user to have the System Privileges, as it will attempt to change DB system settings.
If such privileges cannot be granted the activation can be skipped by using the `--no-alter-system` option.
The command will then print two possible language activation SQL queries, which look like the following:
```sql
ALTER SESSION SET SCRIPT_LANGUAGES=...
ALTER SYSTEM SET SCRIPT_LANGUAGES=...
```
These queries represent two alternative ways of activating a language container. The first one activates the
container at the [Session level](https://docs.exasol.com/db/latest/sql/alter_session.htm). It doesn't require
System Privileges. However, it must be run every time a new session starts. The second one activates the container
at the [System level](https://docs.exasol.com/db/latest/sql/alter_system.htm). It  needs to be run just once,
but it does require System Privileges. It may be executed by a database administrator. Please note, that changes
made at the system level only become effective in new sessions, as described
[here](https://docs.exasol.com/db/latest/sql/alter_system.htm#microcontent1).

It is also possible to activate the language without repeatedly uploading the container. If the container
has already been uploaded one can use the `--no-upload-container` option to skip this step.

By default, overriding language activation is not permitted. If a language with the same alias has already
been activated the command will result in an error. The activation can be overridden with the use of
the `--allow-override` option.
