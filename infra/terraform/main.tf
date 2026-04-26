provider "postgresql" {
  host            = var.db_host
  port            = var.db_port
  database        = var.db_name
  username        = var.db_superuser
  password        = var.db_superuser_password
  sslmode         = "disable"
  connect_timeout = 15
  superuser       = true
}

locals {
  schemas = ["raw", "staging", "intermediate", "marts"]
}

# --- Roles --------------------------------------------------------------

resource "postgresql_role" "dbt_user" {
  name               = "dbt_user"
  login              = true
  password           = var.dbt_user_password
  encrypted_password = true
}

resource "postgresql_role" "readonly_user" {
  name               = "readonly_user"
  login              = true
  password           = var.readonly_user_password
  encrypted_password = true
}

# --- Schemas (owned by dbt_user) ----------------------------------------

resource "postgresql_schema" "layers" {
  for_each = toset(local.schemas)

  name  = each.key
  owner = postgresql_role.dbt_user.name

  # Drop tables/views inside the schema when destroying.
  drop_cascade = true
}

# --- Grants for dbt_user ------------------------------------------------
# dbt_user owns each schema, so it implicitly has full rights, but we make
# the privileges explicit (idempotent re-grant) for documentation and to
# guard against future ownership changes.

resource "postgresql_grant" "dbt_user_schema" {
  for_each = postgresql_schema.layers

  database    = var.db_name
  role        = postgresql_role.dbt_user.name
  schema      = each.value.name
  object_type = "schema"
  privileges  = ["USAGE", "CREATE"]
}

resource "postgresql_grant" "dbt_user_tables" {
  for_each = postgresql_schema.layers

  database    = var.db_name
  role        = postgresql_role.dbt_user.name
  schema      = each.value.name
  object_type = "table"
  privileges  = ["ALL"]
}

resource "postgresql_default_privileges" "dbt_user_tables" {
  for_each = postgresql_schema.layers

  database    = var.db_name
  role        = postgresql_role.dbt_user.name
  schema      = each.value.name
  owner       = postgresql_role.dbt_user.name
  object_type = "table"
  privileges  = ["ALL"]
}

# --- Grants for readonly_user (marts only) ------------------------------

resource "postgresql_grant" "readonly_user_schema" {
  database    = var.db_name
  role        = postgresql_role.readonly_user.name
  schema      = postgresql_schema.layers["marts"].name
  object_type = "schema"
  privileges  = ["USAGE"]
}

resource "postgresql_grant" "readonly_user_tables" {
  database    = var.db_name
  role        = postgresql_role.readonly_user.name
  schema      = postgresql_schema.layers["marts"].name
  object_type = "table"
  privileges  = ["SELECT"]
}

resource "postgresql_default_privileges" "readonly_user_tables" {
  database = var.db_name
  role     = postgresql_role.readonly_user.name
  schema   = postgresql_schema.layers["marts"].name
  # Tables created by dbt_user (the schema owner) should be readable by
  # readonly_user automatically.
  owner       = postgresql_role.dbt_user.name
  object_type = "table"
  privileges  = ["SELECT"]
}
