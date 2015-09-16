#!/usr/bin/env python

# Built-in imports
import argparse
import datetime
import json
import os
import shutil
import subprocess
from time import sleep
import urllib2

# Installed imports.
import paramiko

# Project imports.
from orchestration.ServiceOrchestrator import ServiceOrchestrator
from orchestration.marathon import Marathon

MARATHON_HOST = 'http://las-mesos1.oscar.priv:8080'
MARATHON_JSON = 'http://las-mesos1.oscar.priv:8080/v2/tasks'
SKYLR_HOME = os.environ.get('SKYLR_HOME', '/mnt/skylr/app/skylr')
CONFIG_DIR = '/etc/haproxy/'
USER_CONFIG = os.path.join(CONFIG_DIR, 'haproxy_users.cfg')
CONFIG_DESTINATION = os.path.join(CONFIG_DIR, 'haproxy.auto.cfg')
PID_FILE = '/var/run/haproxy.pid'
SKYLR_TASK_NAME = 'skylr'

HAPROXY_CONFIG_TEMPLATE = os.path.join(SKYLR_HOME, 'etc/haproxy/haproxy.cfg.c0.template')

def getSkylrMarathonInstances():
    req = urllib2.Request(MARATHON_JSON, None, {'Accept': 'application/json'})
    marathonTasks = json.load(urllib2.urlopen(req))['tasks']
    hosts = [{'host': task['host'], 'ports': task['ports']} for task in marathonTasks
            if task['appId'] == SKYLR_TASK_NAME]

    return hosts

def install(marathonHost):
    print "Installing Skylr..."

# TODO: Update this function to use urllib, not the Marathon library
def restart(marathonHost):
    print "Restarting all running instances of Skylr..."

    url = marathonHost or MARATHON_JSON
    client = Marathon(url)
    hosts = [task['host'] for task in json.loads(client.getTasks('skylr'))]

    for host in hosts:
        print 'Killing Skylr task on:', host
        ssh = paramiko.SSHClient()
        ssh.connect(host)
        ssh.command('pkill "node app.js')
        sleep(3)

def refreshConfig ():
    system = ServiceOrchestrator("conf.json")
    tmpConfig =  os.path.join(SKYLR_HOME, 'haproxy.cfg')
    with open(tmpConfig, "w") as output:
        output.write(system.gen ())
    subprocess.call("sudo cp {0} {1}".format(tmpConfig, CONFIG_DESTINATION).split(" "))

def restartLoadBalancer():
    print "{0}: Restarting HAProxy...".format(datetime.datetime.now())

    pid = ""

    if os.path.exists(PID_FILE):
        proc = subprocess.Popen("cat {0}".format(PID_FILE).split(" "), stdout=subprocess.PIPE)
        pid = proc.stdout.read()

    command = "sudo haproxy -f {0} -f {1} -p {2} -D".format(CONFIG_DESTINATION, USER_CONFIG, PID_FILE)

    if pid:
        command = "sudo haproxy -f {0} -f {1} -p {2} -D -st {3}".format(CONFIG_DESTINATION, USER_CONFIG, PID_FILE, pid)

    print "{0}: Restarting HAProxy: {1}".format(datetime.datetime.now(), command)
    subprocess.call(command.split(" "))

def rebalance(marathonHost):
    print "Rebalancing the load balancer..."

    refreshConfig()
    restartLoadBalancer()

def main():
    parser = argparse.ArgumentParser(description='Perform Skylr Node.js app work on Mesos.')
    parser.add_argument('-i', '--install', action='store_true', default=False, dest='install',
        help='install Skylr on the main partition.')
    parser.add_argument('--marathon', type=str, default=MARATHON_HOST,
        help='specify a Marathon master host.')
    parser.add_argument('--restart', action='store_true', default=False, dest='restart',
        help='restart all running instances of Skylr.')
    parser.add_argument('--rebalance', action='store_true', default=False, dest='rebalance',
        help='rebalance the HAProxy loadbalancer.')

    args = parser.parse_args()

    # TODO: May want to run this on a remote host...
    marathonHost = args.marathon or MARATHON_HOST

    if args.install:
        install(marathonHost)

    if args.restart:
        restart(marathonHost)

    if args.rebalance:
        rebalance(marathonHost)


if __name__ == '__main__':
    main()
