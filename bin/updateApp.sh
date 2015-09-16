#!/bin/bash

set -x

host=http://localhost:3030/marathon
appId=skylr
mem=16
cpus=0.1
while test -n "$1"; do
    case "$1" in
        --host)  shift; host="$1"; shift;;
        --appId)   shift; appId="$1"; shift;;
        --instances) shift; instances="$1"; shift;;
        --mem)   shift; mem="$1"; shift;;
        --cpus) shift; cpus="$1"; shift;;
        *)         echo "unrecognized option $1"; exit 1;
    esac
done

request () {
    curl --silent \
        -X POST   \
        -H "Content-Type: application/json" \
        -d "{ \"$appId\" : {
                \"mem\" : \"$mem\",
                \"cpus\" : \"$cpus\",
                \"instances\" : \"$instances\"}
            }" \
        $host
}

request


