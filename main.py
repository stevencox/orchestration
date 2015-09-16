#!/usr/bin/env python

"""
**Skylr Service Orchestrator** is a server that helps orchestrate instances
of jobs managed by our Marathon and Mesos cluster management installations.
It is primarily a [Flask](http://flask.pocoo.org/) server that listens for
several HTTP requests pertaining to Marathon job orchestration.  For example,
it listens for HTTP POST requests from the Marathon server itself that
advertise a "*service_update_event*".

TODO: Make this read the config file for services (e.g. oscar_config.json) every time.
"""

# Built-in imports.
import argparse
import datetime
import json
import logging
import logging.handlers
import os

# Installed imports.
from flask import Flask
from flask import request

# Project imports.
from orchestration.ServiceOrchestrator import ServiceOrchestrator

# Logging for the whole project.
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger('main')

# Constants
CONFIG_FILE = os.environ.get('CONFIG_FILE', '/etc/haproxy/oscar_config.json')

# === Flask Application and Endpoints ===

# The Flask server app.
app = Flask(__name__)
#system = None

@app.route('/marathon', methods=['POST'])
def marathon():
    """
    Endpoint:
        http://[host]:[port]/marathon

    Takes an HTTP POST from Marathon, and if it is a *status_update_event*
    message, we will rewrite the HAProxy configuration and restart HAProxy.
    """
    logger.info("Marathon Event received...")
    updateEvt = json.loads(request.data)

    if updateEvt.get('eventType') != 'status_update_event':
        return 'not status_update_event'

    print 'IP ADDRESS:', request.remote_addr
    system = ServiceOrchestrator(CONFIG_FILE)
    ok = system.reloadHAProxy(request.remote_addr, updateEvt)

    return str(ok)

# TODO: Should this handle an HTTP PUT?
@app.route('/updateApp', methods=['POST'])
def updateApp():
    """
    Flask endpoint for updating an application on Marathon.

    Update the job running the given application(s) on Marathon.  POST body:

        {
            "skylr": {
                "cpus": 0.3,
                "mem": 16,
                "instances": 3
            },
            "extension": {
                "cpus": 0.2,
                "mem": 512,
                "instances": 3
            }
        }

    NOTE: The full [Marathon API](https://mesosphere.github.io/marathon/docs/rest-api.html#put-/v2/apps/%7Bappid%7D)
    allows more parameters to be changed, but we limit them for this API.
    """
    newConfig = json.loads(request.data)
    logger.info('Method called with: {0}'.format(newConfig))

    system = ServiceOrchestrator(CONFIG_FILE)
    ok = system.updateApps(newConfig)

    return 'ok'

# === Server Startup Functions ===

def setupServer():
    # The default PORT will be 3030
    debug = os.environ.get('DEBUG', False)

    # Set some application variables and run.
    app.debug = debug

    #global system
    #if system is None:
    #    system = ServiceOrchestrator(CONFIG_FILE)

def startServer():
    """
    Start the Flask server using some environment varils -al etc
ables.
    """
    setupServer()
    port = os.environ.get('PORT', 3030)

    #system = ServiceOrchestrator(args.configFile)
    system = ServiceOrchestrator(CONFIG_FILE)
    system.startHaproxy()

    app.run(host='0.0.0.0', port=port)

def main():
    """
    The main entrypoint for the server startup script.  Setup and parse some
    command line options, then start the server.
    """
    parser = argparse.ArgumentParser(description='Orchestrate some services')
    parser.add_argument('-c', '--config', type=str, default='/etc/haproxy/oscar_config.json',
        dest='configFile', help='configuration file for the ServiceOrchestrator')
    parser.add_argument('-p', '--pidfile', type=str, default='/var/run/orchestration.pid',
        dest='mPidFile', help='filename to store PID for init.d service operations')

    args = parser.parse_args()

    pid = str(os.getpid())
    f = open(args.mPidFile, 'w')
    f.write(pid)
    f.close()

    logger.info('Orchestrator server starting...')

    startServer()
    
    logger.info("Orchestrator server has stopped...")


if __name__ == '__main__':
   main()
else:
    handler = logging.handlers.SysLogHandler(address='/dev/log', facility=19)
    logger.addHandler(handler)
    setupServer()
