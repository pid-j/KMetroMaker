#!/usr/bin/env bash
fatal() {
    echo "$@" >&2
    exit 1
}

ask-config() {
    read -p "config.toml was not present! Copy from default config? [y/n] " choice
    if [[ "$choice" == "y" || "$choice" == "Y" ]]; then
        cp resources/default.toml config.toml || fatal "Default config does not exist or some other problem has occured!"
    else
        echo "Using default configuration..."
    fi
}

cd "$(dirname "$0")" || fatal "cd failed, somehow..."
[[ -e config.toml ]] || ask-config
[[ -e metro.py ]] || fatal "metro.py is missing, has it been deleted?"
python3 metro.py