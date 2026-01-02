#!/bin/bash
# Simple script to loop through tables found in any non-system namespace
#   excludes tables that are partitions so you only get "main" tables
# Example usage:
#   partitions_for_all_tables.sh | psql "${DATABASE_URI}"
FIND_TABLES="SELECT c.relname AS table_name FROM pg_class c JOIN pg_namespace n ON n.oid = c.relnamespace WHERE c.relkind IN ('r', 'p') AND n.nspname NOT IN ('pg_catalog', 'information_schema') AND c.relispartition = false ORDER BY c.relname;"
for table in $(echo "${FIND_TABLES}" | psql -t "${DATABASE_URI}"); do
    $(dirname $0)/sample_postgresql_partitions_for_table.sh ${table}
done
