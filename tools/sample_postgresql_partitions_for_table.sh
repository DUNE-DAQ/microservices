#!/bin/bash
set -euo pipefail

# Per-table script to generate partition DDL for a single table
# Outputs SQL to stdout for piping to psql or for use by orchestrator script
# Usage:
#   ./sample_postgresql_partitions_for_table.sh <schema.table_name> <year>
# Examples:
#   ./sample_postgresql_partitions_for_table.sh public.users 2025 | psql "${DATABASE_URI}"
#   ./sample_postgresql_partitions_for_table.sh myschema.orders 2025

# Validate arguments
if [[ $# -lt 2 ]]; then
    echo "Error: Missing required arguments" >&2
    echo "Usage: $0 <schema.table_name> <year>" >&2
    exit 1
fi

QUALIFIED_TABLE="$1"
YEAR="$2"

# Parse schema and table name
if [[ "${QUALIFIED_TABLE}" =~ ^([a-zA-Z_][a-zA-Z0-9_]*)\.([a-zA-Z_][a-zA-Z0-9_]*)$ ]]; then
    SCHEMA_NAME="${BASH_REMATCH[1]}"
    TABLE_NAME="${BASH_REMATCH[2]}"
else
    echo "Error: Invalid schema-qualified table name: ${QUALIFIED_TABLE}" >&2
    echo "Expected format: schema.table_name" >&2
    echo "Both schema and table must start with letter/underscore and contain only alphanumeric characters and underscores" >&2
    exit 1
fi

# Validate year
if [[ ! "${YEAR}" =~ ^[0-9]{4}$ ]]; then
    echo "Error: Invalid year: ${YEAR}" >&2
    echo "Year must be a 4-digit number" >&2
    exit 1
fi

# Generate partition DDL
# This is a sample implementation - customize based on your partitioning strategy
cat <<EOF
-- Partitions for table: ${SCHEMA_NAME}.${TABLE_NAME}, year: ${YEAR}
-- Generated on: $(date '+%Y-%m-%d %H:%M:%S')

-- Create monthly partitions for ${YEAR}
DO \$\$
DECLARE
    month_num INT;
    partition_name TEXT;
    start_date DATE;
    end_date DATE;
BEGIN
    FOR month_num IN 1..12 LOOP
        partition_name := '${TABLE_NAME}_' || '${YEAR}' || '_' || LPAD(month_num::TEXT, 2, '0');
        start_date := ('${YEAR}-' || LPAD(month_num::TEXT, 2, '0') || '-01')::DATE;
        end_date := (start_date + INTERVAL '1 month')::DATE;

        -- Check if partition already exists (schema-aware)
        IF NOT EXISTS (
            SELECT 1 FROM pg_class c
            JOIN pg_namespace n ON n.oid = c.relnamespace
            WHERE c.relname = partition_name
              AND n.nspname = '${SCHEMA_NAME}'
        ) THEN
            EXECUTE format(
                'CREATE TABLE IF NOT EXISTS %I.%I PARTITION OF %I.%I FOR VALUES FROM (%L) TO (%L)',
                '${SCHEMA_NAME}',
                partition_name,
                '${SCHEMA_NAME}',
                '${TABLE_NAME}',
                start_date,
                end_date
            );
            RAISE NOTICE 'Created partition: ${SCHEMA_NAME}.%', partition_name;
        ELSE
            RAISE NOTICE 'Partition already exists: ${SCHEMA_NAME}.%', partition_name;
        END IF;
    END LOOP;
END
\$\$;
EOF
