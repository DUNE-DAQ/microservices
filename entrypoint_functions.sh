#!/bin/bash
#######################################
# Validates that required environment variables are defined
# Arguments:
#   Space-separated string of variable names
# Example usage:
#   ensure_required_variables "USER HOME PASSWORD API_TOKEN"
# Returns:
#   0 if all variables are defined
#   3 if any variables are missing
#######################################
function ensure_required_variables() {
    local vars_as_string="${1}"
    local -a vars
    local var
    local missing_variable=0

    # Parse the space-separated variable names
    IFS=' ' read -ra vars <<<"${vars_as_string}"

    echo "Checking for required environment variables..."
    echo "----------------------------------------------"

    # Check each variable
    for var in "${vars[@]}"; do
        # Verify if variable is defined
        if [[ -n "${var}" && -n "${!var-}" ]]; then
            echo "  ${var} is defined"
        else
            echo "  XXX ${var} is NOT defined or empty"
            missing_variable=1
        fi
    done

    echo "----------------------------------------------"

    # Exit if any variables are missing
    if [[ "${missing_variable}" -ne 0 ]]; then
        echo "ERROR: One or more required environment variables are undefined" >&2
        echo "Please define the missing variables and try again" >&2
        exit 3
    fi

    return 0
}
