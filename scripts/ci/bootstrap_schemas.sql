-- CI 専用: Terraform を使わずに schema / role / grant を作る軽量版。
-- main.tf 相当のものを直接 SQL で記述。学習者ローカルでは Terraform を使う。
-- 接続ユーザは superuser (POSTGRES_USER) を想定。

-- --- Roles ---------------------------------------------------------------

DO $$
BEGIN
    IF NOT EXISTS (SELECT FROM pg_catalog.pg_roles WHERE rolname = 'dbt_user') THEN
        CREATE ROLE dbt_user LOGIN PASSWORD 'dbt_password';
    END IF;
    IF NOT EXISTS (SELECT FROM pg_catalog.pg_roles WHERE rolname = 'readonly_user') THEN
        CREATE ROLE readonly_user LOGIN PASSWORD 'readonly_password';
    END IF;
END
$$;

-- --- Schemas (owned by dbt_user) -----------------------------------------

CREATE SCHEMA IF NOT EXISTS raw          AUTHORIZATION dbt_user;
CREATE SCHEMA IF NOT EXISTS staging      AUTHORIZATION dbt_user;
CREATE SCHEMA IF NOT EXISTS intermediate AUTHORIZATION dbt_user;
CREATE SCHEMA IF NOT EXISTS marts        AUTHORIZATION dbt_user;

-- --- Grants for dbt_user -------------------------------------------------

GRANT USAGE, CREATE ON SCHEMA raw, staging, intermediate, marts TO dbt_user;

-- (table-level grants are unnecessary because dbt_user owns the schemas;
-- listed for parity with main.tf documentation intent)

-- --- Grants for readonly_user (marts only) -------------------------------

GRANT USAGE  ON SCHEMA marts TO readonly_user;
GRANT SELECT ON ALL TABLES IN SCHEMA marts TO readonly_user;

ALTER DEFAULT PRIVILEGES FOR ROLE dbt_user IN SCHEMA marts
    GRANT SELECT ON TABLES TO readonly_user;
