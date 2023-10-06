
function ensure_required_variables() {

    vars_as_string=$1
    
    IFS=' ' read -ra vars <<< "$vars_as_string"

    missing_variable=false
    
    for var in "${vars[@]}"; do

	if [[ -v $var ]]; then
	    echo "$var is defined as \"${!var}\"."
	else
	    echo "$var needs to be defined as an environment variable."
	    missing_variable=true
	fi
    done

    if $missing_variable ; then
	echo "One or more required environment variables is undefined; exiting..." >&2
	exit 3
    fi
}
