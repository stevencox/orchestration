#!/bin/bash
#
# For optimal results, run this from the base skyr-orchestration directory,
# e.g.:
#
# ./bin/orch.sh setup
# ./bin/orch.sh docs
# sudo -E ./bin/orch.sh run dev -c ./etc/local_config.json
#

# Environment variables
VENV=/mnt/skylr/orchestration/v-orch
MAIN_PROJ=main
MAIN_APP=$MAIN_PROJ:app
ALL_PYs="./*.py ./bin/*.py ./orchestration/*.py ./test/*.py"
ALL_PYCs="./*.pyc ./bin/*.pyc ./orchestration/*.pyc ./test/*.pyc"

# Conditionally set environment variables
[ -z $PORT ] && PORT=3030

# 1) Create a Python virtual environ
# 2) Install the requirements from requirements.txt
function setup () {
    virtualenv $VENV
    activate_venv;
    pip install -r requirements.txt
}

function activate_venv () {
    source $VENV/bin/activate
}

function docs () {
    activate_venv;
    pycco $ALL_PYs
    echo ""
    echo "Visit the following URL for documentation:"
    echo -e "file://$(realpath ./docs)"
    echo ""
}

function lint () {
    pylint -E $ALL_PYs
}

function clean () {
    rm $ALL_PYCs
    rm -rf $VENV
    rm -rf ./docs
}

function test () {
    coverage run test/orch_tests.py
}

function cover  () {
    test;
    coverage report -m | grep -v "v-orch"
}

# Run either production or dev
function run () {
    activate_venv;

    # In production, use gunicorn
    # NOTE: If you run this locally, then set the CONFIG_FILE correctly:
    # > export CONFIG_FILE=./etc/local_config.json
    # > ./bin/orch.sh run prod
    prod () {
        echo Running production...
        [ -z $CONFIG_FILE ] && export CONFIG_FILE=/etc/haproxy/oscar_config.json;
        gunicorn -D -b 0.0.0.0:$PORT $MAIN_APP;
    }

    # In development, use the Flask dev server in the server module
    # Example:
    # > ./bin/orch.sh run dev --config ./etc/local_config.json
    dev () {
        echo Running dev...
        echo PLEASE NOTE, this script should be run with sudo
        export DEBUG=True
        cd /mnt/skylr/orchestration
        python -m $MAIN_PROJ "$@" > /var/log/skylr-orchestration/skylr-orchestration.log 2>&1 &
    }

    $*
}

$*
