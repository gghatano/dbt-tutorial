variable "db_host" {
  description = "PostgreSQL host. Defaults to localhost for the docker-compose container exposed on the host."
  type        = string
  default     = "localhost"
}

variable "db_port" {
  description = "PostgreSQL port published by docker-compose."
  type        = number
  default     = 5432
}

variable "db_name" {
  description = "Target database name. Provisioned by docker-compose via POSTGRES_DB."
  type        = string
  default     = "analytics"
}

variable "db_superuser" {
  description = "Bootstrap role used by Terraform to create schemas/roles. Created by POSTGRES_USER."
  type        = string
  default     = "analytics_user"
}

variable "db_superuser_password" {
  description = "Password for db_superuser. Defaulted for local learning use only — override in real environments."
  type        = string
  sensitive   = true
  default     = "analytics_password"
}

variable "dbt_user_password" {
  description = "Password assigned to the dbt_user login role. Local-learning default."
  type        = string
  sensitive   = true
  default     = "dbt_password"
}

variable "readonly_user_password" {
  description = "Password assigned to the readonly_user login role. Local-learning default."
  type        = string
  sensitive   = true
  default     = "readonly_password"
}
