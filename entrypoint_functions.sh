function ensure_required_variables() {
    local vars_as_string=$1

    IFS=' ' read -ra vars <<<"$vars_as_string"

    for var in "${vars[@]}"; do
        if [[ -v $var ]]; then
            echo "$var is defined as \"${!var}\"."
        else
            echo "$var needs to be defined as an environment variable."
            echo "One or more required environment variables is undefined; exiting..." >&2
            exit 3
        fi
    done
}
