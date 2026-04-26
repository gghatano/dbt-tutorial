output "schemas" {
  description = "Names of schemas created/managed by this Terraform configuration."
  value       = [for s in postgresql_schema.layers : s.name]
}

output "roles" {
  description = "Names of login roles created/managed by this Terraform configuration."
  value = [
    postgresql_role.dbt_user.name,
    postgresql_role.readonly_user.name,
  ]
}

output "db_endpoint" {
  description = "host:port endpoint for the managed PostgreSQL instance."
  value       = "${var.db_host}:${var.db_port}"
}
