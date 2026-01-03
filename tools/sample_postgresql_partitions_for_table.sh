#!/bin/bash
set -euo pipefail

TABLE_NAME="${1:-example}"
YEAR="${2:-$(date '+%Y')}"

START_DATE="${YEAR}-01-01"

# Calculate cutoff date (9 days ago)
CUTOFF_DATE=$(date -d "9 days ago" +%Y-%m-%d)
CUTOFF_TIMESTAMP=$(date -d "${CUTOFF_DATE}" +%s)

# Function to check if a date is after the cutoff
is_after_cutoff() {
    local check_date=$1
    local check_timestamp=$(date -d "${check_date}" +%s)
    [[ ${check_timestamp} -gt ${CUTOFF_TIMESTAMP} ]]
}

# Function to extract end date from partition SQL
extract_end_date() {
    local partition_sql=$1
    echo "${partition_sql}" | grep -oP "TO \('\K[^']+"
}

# Function to build partition SQL
build_partition() {
    local table=$1
    local year=$2
    local week=$3
    local start=$4
    local end=$5

    echo "CREATE TABLE IF NOT EXISTS \"${table}_year${year}_week${week}\" PARTITION OF \"${table}\" FOR VALUES FROM ('${start}') TO ('${end}');"
}

# Function to output partition if it passes cutoff check
output_partition_if_valid() {
    local partition_sql=$1

    if [[ -n "${partition_sql}" ]]; then
        local end_date=$(extract_end_date "${partition_sql}")
        if is_after_cutoff "${end_date}"; then
            echo -e "${partition_sql}"
        fi
    fi
}

start_week=${START_DATE}
week_number=0
previous_partition=""

# Validate table name contains only alphanumeric, underscore
if [[ ! "${TABLE_NAME}" =~ ^[a-zA-Z_][a-zA-Z0-9_]*$ ]]; then
    echo "Error: Invalid table name '${TABLE_NAME}'" >&2
    exit 1
fi

# Reject reserved prefixes
if [[ "${TABLE_NAME}" =~ ^pg_ ]]; then
    echo "Error: Table name '${TABLE_NAME}' uses reserved 'pg_' prefix" >&2
    exit 1
fi

# Validate table name length (PostgreSQL limit is 63 bytes) leave extra space for expansion
TABLE_NAME_BYTES=$(echo -n "${TABLE_NAME}" | wc -c)
if [[ ${TABLE_NAME_BYTES} -gt 45 ]]; then
    echo "Error: Table name '${TABLE_NAME}' (${TABLE_NAME_BYTES} bytes) exceeds 45-byte limit with suffix" >&2
    exit 1
fi

# Validate YEAR is a 4-digit number
if [[ ! "${YEAR}" =~ ^[0-9]{4}$ ]]; then
    echo "Error: Invalid year '${YEAR}' (must be 4 digits)" >&2
    exit 1
fi

echo "BEGIN TRANSACTION;"
for count in {1..60}; do
    week_number=$((week_number + 1))
    week_count_string=$(printf "%02d" ${week_number})

    # Calculate end of week (7 days later)
    end_week=$(date -d "${start_week} + 7 days" +%Y-%m-%d)

    start_week_year=$(date -d "${start_week}" +%Y)
    end_week_year=$(date -d "${end_week}" +%Y)

    # Check if we've crossed into a new year
    if [[ ${start_week_year} -ne ${end_week_year} ]]; then
        # Calculate how many days remain in the current year
        year_end=$(date -d "${start_week_year}-12-31" +%Y-%m-%d)
        days_remaining=$((($(date -d "${year_end}" +%s) - $(date -d "${start_week}" +%s)) / 86400 + 1))

        if [[ ${days_remaining} -le 3 ]]; then
            # Merge short final week into previous week by extending to new year boundary
            end_week=$(date -d "${start_week_year}-12-31 + 1 day" +%Y-%m-%d)

            # Output the extended previous week if valid
            if is_after_cutoff "${end_week}"; then
                echo "${previous_partition}" | sed "s/) TO ('[^']*');/) TO ('${end_week}');/"
            fi

            # Start next week at the new year, reset week counter
            start_week=${end_week}
            week_number=0
            previous_partition=""
        else
            # Output the previous partition if valid
            output_partition_if_valid "${previous_partition}"

            # Create final week of year going to year boundary
            end_week=$(date -d "${start_week_year}-12-31 + 1 day" +%Y-%m-%d)

            previous_partition=$(build_partition "${TABLE_NAME}" "${start_week_year}" "${week_count_string}" "${start_week}" "${end_week}")

            # Start next week at the new year, reset week counter
            start_week=${end_week}
            week_number=0
        fi
    else
        # Output the previous partition if valid
        output_partition_if_valid "${previous_partition}"

        # Store current partition
        previous_partition=$(build_partition "${TABLE_NAME}" "${start_week_year}" "${week_count_string}" "${start_week}" "${end_week}")

        start_week=${end_week}
    fi

done

# Output final partition if valid
output_partition_if_valid "${previous_partition}"

echo "END TRANSACTION;"
