{#-
    Override of dbt's built-in `generate_schema_name` macro.

    Default behaviour concatenates `target.schema` with the configured custom
    schema (e.g. `+schema: marts` becomes `<target_schema>_marts`). For this
    project we want each layer's schema to map 1:1 to the Postgres schemas
    created by Terraform (`raw`, `staging`, `intermediate`, `marts`), so we
    return `custom_schema_name` verbatim when it is provided.

    See docs/decisions/0005-dbt-config.md for context.
-#}
{% macro generate_schema_name(custom_schema_name, node) -%}
    {%- if custom_schema_name is none -%}
        {{ target.schema }}
    {%- else -%}
        {{ custom_schema_name | trim }}
    {%- endif -%}
{%- endmacro %}
