#!/bin/sh
set -eu
# Fresh development volumes only. psql variable quoting prevents password interpolation into SQL.
psql --username "$POSTGRES_USER" --dbname postgres --set ON_ERROR_STOP=1 \
  --set control_owner_password="$CONTROL_OWNER_PASSWORD" \
  --set control_app_password="$CONTROL_APP_PASSWORD" \
  --set warehouse_owner_password="$WAREHOUSE_OWNER_PASSWORD" \
  --set superset_owner_password="$SUPERSET_OWNER_PASSWORD" <<'SQL'
CREATE ROLE control_owner LOGIN PASSWORD :'control_owner_password' NOSUPERUSER NOCREATEDB NOCREATEROLE;
CREATE ROLE control_app LOGIN PASSWORD :'control_app_password' NOSUPERUSER NOCREATEDB NOCREATEROLE;
CREATE ROLE warehouse_owner LOGIN PASSWORD :'warehouse_owner_password' NOSUPERUSER NOCREATEDB NOCREATEROLE;
CREATE ROLE superset_owner LOGIN PASSWORD :'superset_owner_password' NOSUPERUSER NOCREATEDB NOCREATEROLE;
CREATE DATABASE control OWNER control_owner;
CREATE DATABASE warehouse OWNER warehouse_owner;
CREATE DATABASE superset OWNER superset_owner;
REVOKE ALL ON DATABASE control FROM PUBLIC;
REVOKE ALL ON DATABASE warehouse FROM PUBLIC;
REVOKE ALL ON DATABASE superset FROM PUBLIC;
GRANT CONNECT ON DATABASE control TO control_owner, control_app;
GRANT CONNECT ON DATABASE warehouse TO warehouse_owner;
GRANT CONNECT ON DATABASE superset TO superset_owner;
\connect control
REVOKE ALL ON SCHEMA public FROM PUBLIC;
GRANT USAGE, CREATE ON SCHEMA public TO control_owner;
GRANT USAGE ON SCHEMA public TO control_app;
ALTER DEFAULT PRIVILEGES FOR ROLE control_owner IN SCHEMA public GRANT SELECT, INSERT, UPDATE, DELETE ON TABLES TO control_app;
ALTER DEFAULT PRIVILEGES FOR ROLE control_owner IN SCHEMA public GRANT USAGE, SELECT ON SEQUENCES TO control_app;
\connect warehouse
REVOKE ALL ON SCHEMA public FROM PUBLIC;
GRANT USAGE, CREATE ON SCHEMA public TO warehouse_owner;
\connect superset
REVOKE ALL ON SCHEMA public FROM PUBLIC;
GRANT USAGE, CREATE ON SCHEMA public TO superset_owner;
SQL
