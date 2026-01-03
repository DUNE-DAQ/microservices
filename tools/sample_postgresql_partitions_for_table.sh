#!/bin/bash
set -euo pipefail

# Per-table script to generate partition DDL for a single table
# Outputs SQL to stdout for piping to psql or for use by orchestrator script
# Usage:
#   ./sample_postgresql_partitions_for_table.sh <table_name> <year>
# Examples:
#   ./sample_postgresql_partitions_for_table.sh users 2025 | psql "${DATABASE_URI}"
#   ./sample_postgresql_partitions_for_table.sh orders 2025

# Validate arguments
if [[ $# -lt 2 ]]; then
    echo "Error: Missing required arguments" >&2
    echo "Usage: $0 <table_name> <year>" >&2
    exit 1
fi

TABLE_NAME="$1"
YEAR="$2"

# Validate table name (basic SQL injection prevention)
if [[ ! "${TABLE_NAME}" =~ ^[a-zA-Z_][a-zA-Z0-9_]*$ ]]; then
    echo "Error: Invalid table name: ${TABLE_NAME}" >&2
    echo "Table name must start with letter/underscore and contain only alphanumeric characters and underscores" >&2
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
-- Partitions for table: ${TABLE_NAME}, year: ${YEAR}
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

        -- Check if partition already exists
        IF NOT EXISTS (
            SELECT 1 FROM pg_class c
            JOIN pg_namespace n ON n.oid = c.relnamespace
            WHERE c.relname = partition_name
        ) THEN
            EXECUTE format(
                'CREATE TABLE IF NOT EXISTS %I PARTITION OF ${TABLE_NAME} FOR VALUES FROM (%L) TO (%L)',
                partition_name,
                start_date,
                end_date
            );
            RAISE NOTICE 'Created partition: %', partition_name;
        ELSE
            RAISE NOTICE 'Partition already exists: %', partition_name;
        END IF;
    END LOOP;
END
\$\$;
EOF
