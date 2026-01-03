#!/bin/bash
set -euo pipefail

# Simple script to loop through tables found in any non-system namespace
#   excludes tables that are partitions so you only get "main" tables
# Example usage:
#   partitions_for_all_tables.sh | psql "${DATABASE_URI}" -v ON_ERROR_STOP=1
# Optionally set YEAR environment variable (defaults to current year in per-table script)

SCRIPT_DIR="$(cd "$(dirname "$(readlink -f "${BASH_SOURCE[0]}")")" && pwd)"
YEAR="${YEAR:-$(date '+%Y')}"

# Array to collect errors
declare -a ERRORS=()

# Function to find all non-system, non-partition tables
find_tables() {
    local query="SELECT c.relname AS table_name
FROM pg_class c
JOIN pg_namespace n ON n.oid = c.relnamespace
WHERE c.relkind IN ('r', 'p')
  AND n.nspname NOT IN ('pg_catalog', 'information_schema')
  AND c.relispartition = false
ORDER BY c.relname;"

    echo "${query}"
}

# Function to add error with context
add_error() {
    local error_msg="$1"
    ERRORS+=("${error_msg}")
}

# Validate DATABASE_URI
if [[ -z "${DATABASE_URI:-}" ]]; then
    echo "Error: DATABASE_URI environment variable is not set" >&2
    exit 1
fi

# Validate per-table script exists
PARTITION_SCRIPT="${SCRIPT_DIR}/sample_postgresql_partitions_for_table.sh"
if [[ ! -f "${PARTITION_SCRIPT}" ]]; then
    echo "Error: Script not found: ${PARTITION_SCRIPT}" >&2
    exit 1
fi

if [[ ! -x "${PARTITION_SCRIPT}" ]]; then
    echo "Error: Script is not executable: ${PARTITION_SCRIPT}" >&2
    exit 1
fi

# Test database connection
if ! psql "${DATABASE_URI}" -c "SELECT 1" >/dev/null 2>&1; then
    echo "Error: Cannot connect to database using DATABASE_URI" >&2
    exit 1
fi

# Fetch table list
TABLES_OUTPUT=$(find_tables | psql -t -q "${DATABASE_URI}") || {
    echo "Error: Failed to query tables from database" >&2
    echo "Query output: ${TABLES_OUTPUT}" >&2
    exit 1
}

# Count total tables for progress tracking
TOTAL_TABLES=$(echo "${TABLES_OUTPUT}" | grep -v '^[[:space:]]*$' | wc -l)
CURRENT=0

if [[ ${TOTAL_TABLES} -eq 0 ]]; then
    echo "Warning: No tables found in database" >&2
    exit 0
fi

echo "Processing ${TOTAL_TABLES} tables for year ${YEAR}..." >&2

# Process each table
while IFS= read -r table; do
    # Skip empty lines
    [[ -z "${table}" ]] && continue

    # Trim whitespace
    table=$(echo "${table}" | xargs)
    [[ -z "${table}" ]] && continue

    CURRENT=$((CURRENT + 1))
    echo "[$CURRENT/$TOTAL_TABLES] Processing table: ${table}" >&2

    # Execute partition script and capture errors
    if ! "${PARTITION_SCRIPT}" "${table}" "${YEAR}"; then
        add_error "Table '${table}': Failed to create/manage partitions"
    fi
done <<<"${TABLES_OUTPUT}"

# Report errors at the end
if [[ ${#ERRORS[@]} -gt 0 ]]; then
    echo "" >&2
    echo "======================================" >&2
    echo "ERRORS ENCOUNTERED (${#ERRORS[@]} total):" >&2
    echo "======================================" >&2
    for error in "${ERRORS[@]}"; do
        echo "  • ${error}" >&2
    done
    echo "======================================" >&2
    exit 1
else
    echo "" >&2
    echo "Successfully processed all ${TOTAL_TABLES} tables." >&2
    exit 0
fi
