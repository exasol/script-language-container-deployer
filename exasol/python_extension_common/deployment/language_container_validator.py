from __future__ import annotations
from typing import Generator
from datetime import timedelta
import random
import string
from contextlib import contextmanager
from textwrap import dedent

from tenacity import retry
from tenacity.wait import wait_fixed
from tenacity.stop import stop_after_delay, stop_after_attempt

import pyexasol     # type: ignore

_DUMMY_UDF_NAME = 'DUMMY_UDF'


def _get_test_udf_name(schema: str | None) -> str:

    if schema:
        return f'"{schema}"."{_DUMMY_UDF_NAME}"'
    return f'"{_DUMMY_UDF_NAME}"'


def _create_dummy_udf(conn: pyexasol.ExaConnection, language_alias: str,
                      schema: str | None) -> None:

    # The dummy UDF returns the ID of the node it is running at.
    udf_name = _get_test_udf_name(schema)
    sql = dedent(f"""
    CREATE OR REPLACE {language_alias} SET SCRIPT {udf_name}(i DECIMAL(10, 0))
    RETURNS DECIMAL(10, 0) AS

    def run(ctx):
        return exa.meta.node_id
    /
    """)
    conn.execute(sql)


def _call_dummy_udf(conn: pyexasol.ExaConnection, schema: str | None) -> None:

    # First, need to find out the number of nodes.
    sql = "SELECT NPROC();"
    nproc = conn.execute(sql).fetchval()

    # This query should run the dummy udf on all nodes.
    udf_name = _get_test_udf_name(schema)
    sql = dedent(f"""
    SELECT {udf_name}(i) FROM VALUES BETWEEN 1 AND {nproc} t(i)
    GROUP BY i;
    """)
    # The expected result is a collection of distinct node IDs from 0 to nproc - 1.
    result = conn.execute(sql).fetchall()
    set_result = {row[0] for row in result}

    assert set_result == set(range(nproc))


def _delete_dummy_udf(conn: pyexasol.ExaConnection, schema: str | None) -> None:

    udf_name = _get_test_udf_name(schema)
    sql = dedent(f"""
    DROP SCRIPT IF EXISTS {udf_name};
    """)
    conn.execute(sql)


@retry(reraise=True, stop=stop_after_attempt(3))
def _create_random_schema(conn: pyexasol.ExaConnection, schema_name_length: int) -> str:

    schema = ''.join(random.choice(string.ascii_letters)
                     for _ in range(schema_name_length))
    sql = f'CREATE SCHEMA "{schema}";'
    conn.execute(query=sql)
    return schema


def _delete_schema(conn: pyexasol.ExaConnection, schema: str) -> None:

    sql = f'DROP SCHEMA IF EXISTS "{schema}" CASCADE;'
    conn.execute(query=sql)


def validate_language_container(conn: pyexasol.ExaConnection,
                                language_alias: str,
                                schema: str | None = None
                                ) -> None:
    """
    Runs a test to check if a language container has been installed and is now
    operational. Will raise an exception if this is not the case.

    conn            - pyexasol connection. The language container must be activated either
                    at the SYSTEM level or at the SESSION associated with this connection.
    language_alias  - Language alias of the language container.
    schema          - The schema to run the tests in. If not specified the current schema
                    is assumed.
    """
    try:
        _create_dummy_udf(conn, language_alias, schema)
        _call_dummy_udf(conn, schema)
    finally:
        _delete_dummy_udf(conn, schema)


def wait_language_container(conn: pyexasol.ExaConnection,
                            language_alias: str,
                            schema: str | None = None,
                            timeout: timedelta = timedelta(minutes=5),
                            interval: timedelta = timedelta(seconds=5),
                            ) -> None:
    """
    Keeps calling validate_language_container until it succeeds or the timeout expires.

    conn            - pyexasol connection. The language container must be activated either
                    at the SYSTEM level or at the SESSION associated with this connection.
    language_alias  - Language alias of the language container.
    schema          - The schema to run the tests in. If not specified the current schema
                    is assumed.
    timeout         - Will give up after this timeout expires. The last exception thrown
                    by the validate_language_container will be re-raised.
    interval        - The calls to validate_language_container are spaced by this time
                    interval.
    """
    @retry(reraise=True, wait=wait_fixed(interval), stop=stop_after_delay(timeout))
    def repeat_validate_language_container():
        validate_language_container(conn, language_alias, schema)

    repeat_validate_language_container()


@contextmanager
def temp_schema(conn: pyexasol.ExaConnection,
                schema_name_length: int = 20
                ) -> Generator[str, None, None]:
    """
    A context manager for running an operation in a newly created temporary schema.
    The schema will be deleted after the operation is competed. Note, that all objects
    created in this schema will be deleted with it. Returns the name of the created schema.

    conn                - pyexasol connection.
    schema_name_length  - Number of characters in the temporary schema name.
    """
    schema = ''
    try:
        schema = _create_random_schema(conn, schema_name_length)
        yield schema
    finally:
        _delete_schema(conn, schema)
