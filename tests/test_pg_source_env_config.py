"""
Tests for ``PostgresBuildingSource``'s environment-variable-driven
connection config (2026-08-16) -- no real Postgres connection needed,
these only exercise constructor argument resolution.

Regression guard for the previous behavior: silent hardcoded defaults
(``localhost``/``postgres``/``postgres``/``city2tabula_germany``) meant a
misconfigured environment would happily attempt a connection with wrong
credentials rather than fail clearly up front. Now database/user/password
are required (explicit arg or env var) and raise immediately if neither
is set.
"""
from __future__ import annotations

import pytest

from buem.buildings.datasources.pg_source import PostgresBuildingSource, psycopg2

requires_psycopg2 = pytest.mark.skipif(
    psycopg2 is None, reason="psycopg2 not installed",
)


@requires_psycopg2
def test_missing_credentials_raises_clear_error(monkeypatch):
    for var in ("BUEM_PG_HOST", "BUEM_PG_PORT", "BUEM_PG_DATABASE", "BUEM_PG_USER", "BUEM_PG_PASSWORD"):
        monkeypatch.delenv(var, raising=False)

    with pytest.raises(ValueError, match="BUEM_PG_DATABASE"):
        PostgresBuildingSource()


@requires_psycopg2
def test_explicit_args_override_env_vars(monkeypatch):
    monkeypatch.setenv("BUEM_PG_DATABASE", "env_db")
    monkeypatch.setenv("BUEM_PG_USER", "env_user")
    monkeypatch.setenv("BUEM_PG_PASSWORD", "env_pass")

    source = PostgresBuildingSource(database="explicit_db", user="explicit_user", password="explicit_pass")

    assert source._conn_params["database"] == "explicit_db"
    assert source._conn_params["user"] == "explicit_user"
    assert source._conn_params["password"] == "explicit_pass"


@requires_psycopg2
def test_env_vars_used_when_no_explicit_args(monkeypatch):
    monkeypatch.setenv("BUEM_PG_HOST", "example-host")
    monkeypatch.setenv("BUEM_PG_PORT", "5433")
    monkeypatch.setenv("BUEM_PG_DATABASE", "env_db")
    monkeypatch.setenv("BUEM_PG_USER", "env_user")
    monkeypatch.setenv("BUEM_PG_PASSWORD", "env_pass")

    source = PostgresBuildingSource()

    assert source._conn_params == {
        "host": "example-host",
        "port": 5433,
        "database": "env_db",
        "user": "env_user",
        "password": "env_pass",
    }


@requires_psycopg2
def test_host_and_port_default_when_unset(monkeypatch):
    monkeypatch.delenv("BUEM_PG_HOST", raising=False)
    monkeypatch.delenv("BUEM_PG_PORT", raising=False)
    monkeypatch.setenv("BUEM_PG_DATABASE", "env_db")
    monkeypatch.setenv("BUEM_PG_USER", "env_user")
    monkeypatch.setenv("BUEM_PG_PASSWORD", "env_pass")

    source = PostgresBuildingSource()

    assert source._conn_params["host"] == "localhost"
    assert source._conn_params["port"] == 5432
