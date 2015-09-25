#!/usr/bin/env python

"""
**ServiceOrchestrator** is a module devoted to reading an environment
configuration file, and writing an HAProxy configuration upon demand.
At present, it uses the **Marathon** module to gather information about
the applications that it is configured to write HAProxy sections for.
"""

import datetime
import json
import logging
import os
import socket
from string import Template
import subprocess

from marathon import Marathon

logger = logging.getLogger('ServiceOrchestrator')
handler = logging.handlers.SysLogHandler(address='/dev/log', facility=19)
logger.addHandler(handler)
ORCH_HOME = os.environ.get('ORCH_HOME', '/opt/app/orchestration')

class ServiceOrchestrator(object):

# === HAProxy Template Variables ===

    configT = Template("""
global
    log         127.0.0.1 local0
    log         127.0.0.1 local1 debug
    log-send-hostname
    chroot      /var/lib/haproxy
    pidfile     /var/run/haproxy.pid
    maxconn     4000
    user        haproxy
    group       haproxy
    daemon
    stats socket /var/lib/haproxy/stats

defaults
    mode                    http
    log                     global
    option                  httplog
    option                  dontlognull
    option http-server-close
    option forwardfor       except 127.0.0.0/8
    option                  redispatch
    retries                 3
    timeout http-request    10s
    timeout connect         10s
    timeout queue           1m
    timeout server          1m
    timeout tunnel          1h
    timeout client          1m
    timeout http-keep-alive 10s
    timeout check           10s
    maxconn                 3000

listen stats *:8082
    stats enable
    stats auth     username:password
    stats uri      /proxy_stats
    stats realm    PAGE TITLE
${services}
""")

    httpT = Template("""
frontend http-in-${id}
    bind :${port}
#    reqadd X-Forwarded-Proto:\ https
    acl is_websocket hdr(Connection)  -i Upgrade
    acl is_websocket path_beg /socket.io
    acl is_websocket hdr(Upgrade) -i WebSocket
    use_backend websocket-${id} if is_websocket #is_connection
    default_backend www-${id}
backend www-${id}
    timeout server 30s
    balance roundrobin
    option httpclose
    option http-server-close
$auth
${httpServices}""")

    wsT = Template("""backend websocket-${id}
    mode http
    balance leastconn
    timeout server 600s
    option forwardfor
    option http-server-close
    option forceclose
    no option httpclose
    cookie WEBSOCKETSERV insert indirect nocache preserve
    appsession WEBSOCKETSERV len 52 timeout 3h request-learn
${wsServices}
""")

    authT = Template("""    acl auth_ok http_auth(${authConf})
    http-request auth unless auth_ok
""")
    httpTask = Template("    server service-${id} ${host}:${port}\n")
    wsTask = Template("    server service-${id} ${host}:${port} cookie service-${id} weight 1 maxconn 8192 check\n")

    def __init__(self, config, marathonHost=None):
        with open (config) as stream:
            self.config = json.loads(stream.read())

        if marathonHost:
            self.marathonHost = 'http://' + marathonHost + ':8080/v2'
        else:
            self.marathonHost = 'http://' + self.config['marathon_hosts'][0] + '/v2'

        self.cluster        = Marathon(self.marathonHost)
        self.services       = self.config['services']
        self.configDest     = self.config['config_destination']
        self.usersConfig    = self.config['users_config_destination']
        self.pidFile        = self.config['pid_file']
        self.approvedHosts  = self.resolveHosts()

    def resolveHosts(self):
        hosts = []

        for host in self.config['marathon_hosts']:
            host = host.split(':')[0]
 	    print 'host = ', host
            hosts.append(socket.gethostbyname(host))

        return hosts

    def startHaproxy(self):
        ipAddr = self.approvedHosts[0]
        appId = self.config['services'].keys()[0]

        self.reloadHAProxy(ipAddr, {'appId': appId })

    def validRequest(self, ipAddr, appId):
        return self.isAppTracked(appId) and self.isApprovedHost(ipAddr)

    def isApprovedHost(self, ipAddr):
        approved = ipAddr in self.approvedHosts
        logger.info ("Approved host {0}: {1}".format (ipAddr, approved))
        return approved

    def isAppTracked(self, appId):
        tapp = appId[1:] if appId.startswith ('/') else appId
        logger.info ("Testing is tracked for {0}".format (tapp))
        logger.info ("services: {0}".format (self.services))
        tracked = tapp in self.services
        logger.info ("Tracked: {0}".format (tracked))
        return tracked

    def gen(self):
        apps = self.cluster.getApps()
        services = []

        for app in apps:
            appId = app['id']

            appId = appId[1:] if appId.startswith ('/') else appId

            if not appId in self.services:
                logger.info ("Ignoring app {0} not in listed services".format (appId))
                continue

            app = self.services[appId]
            port = app['port']
            backend_port = None
            single_host = None

            if 'backend_port' in app:
                backend_port = app['backend_port']
            if 'single_host' in app:
                single_host = app['single_host']


            lines = []
            wsLines = []

            if appId in self.services.keys():
                tasks = self.cluster.getTasks(appId)
                c = 0

                if single_host:
                        print "WARNING: Using single host for:", appId
                        context = {
                            "id" : "%s-%s" % ('app', appId),
                            "host" : single_host,
                            "port" : backend_port
                        }
                        lines.append(self.httpTask.substitute(context))
                        wsLines.append(self.wsTask.substitute(context))
                else:
                    for task in tasks:
                        # NOTE: The method of getting the appId below is quirky to support
                        # two different versions of marathon. The latest uses 'appId'.
                        aid = task.get('appId', task.get('appID', 'app'))
                        aid = aid[1:] if aid.startswith ('/') else iad
                        context = {
                            "id" : "%s-%s" % (aid, c),
                            "host" : task['host'],
                            "port" : backend_port if backend_port else task['ports'][0]
                        }

                        lines.append(self.httpTask.substitute(context))
                        wsLines.append(self.wsTask.substitute(context))
                        c += 1

            auth = ""

            if 'authConf' in app:
                auth = self.authT.substitute(app)

            httpService = self.httpT.substitute({
                "id" : appId,
                "port" : port,
                "auth" : auth,
                "httpServices" : ''.join(lines)
            })

            wsService = self.wsT.substitute({
                "id" : appId,
                "port" : port,
                "wsServices" : ''.join(wsLines)
            })

            services.append('{0}{1}'.format(httpService, wsService))

        return self.configT.substitute({ "services" : "".join(services) })

    def refreshConfig(self):
        configText = self.gen()
        tmpConfig = self.writeTmpConfig(configText)

        logger.info("Copying temp config to destination: {0}".format(self.configDest))
        subprocess.call("cp {0} {1}".format(tmpConfig, self.configDest).split(" "))

        return True

    def writeTmpConfig(self, configText):
        """
        A method to write the temporary config file.
        """
        tmpConfig = os.path.join(ORCH_HOME, 'haproxy.cfg')

        with open(tmpConfig, "w") as output:
            output.write(configText)

        return tmpConfig

    def restartHAProxy(self):
        logger.info("Restarting HAProxy...")
        pid = ""

        if os.path.exists(self.pidFile):
            proc = subprocess.Popen("cat {0}".format(self.pidFile).split(" "),
                stdout=subprocess.PIPE)
            pid = proc.stdout.read()

#        command = "haproxy -f {0} -f {1} -p {2} -D".format(
#            self.configDest, self.usersConfig, self.pidFile)
        command = "sudo haproxy -f {0} -p {1} -D".format(
            self.configDest, self.pidFile)

        if pid:
            command = "sudo haproxy -f {0} -p {1} -D -st {2}".format(
                self.configDest, self.pidFile, pid)

        logger.info("Restarting HAProxy with commmand: {0}".format(command))
        subprocess.call(command.split(" "))

        return True

    def reloadHAProxy(self, ipAddr, updateEvt):
        # NOTE: The method of getting the appId below is quirky, to support
        # two different versions of marathon. The latest uses 'appId'.
        appId = updateEvt.get('appId', updateEvt.get('appID', 'app'))
        logger.info('reloadHaproxy received event from [{0}] for appId [{1}]'.format(
            str(ipAddr), appId))

        # TODO: Should probably throw an error here.
        if not self.validRequest(ipAddr, appId):
            logger.info('reloadHaproxy rejecting invalid event')
            return False

        logger.info('App is tracked, and host is correct, proceeding with config rewrite...')

        ok = self.refreshConfig()
        if ok:
            self.restartHAProxy()

        return ok

    def updateApp(self, appId, newConfig):
        """
        Updates the given app with the new configuration.

        Example:
            appId: "skylr"
            newConfig: { "cpus": 0.3, "mem": 16, "instances": 3 }

        TODO: Do we do anything to limit the hosts that can update Apps?
        """
        ok = False
        if self.isAppTracked(appId):
            ok = self.cluster.updateApp(appId, newConfig)
        else:
            logger.info('Not a valid updateApp request for [{0}] config: [{1}]'.
                format(appId, newConfig))

        return ok

    def updateApps(self, config):
        """
        Take configurations for multiple apps in a dictionary, and apply them
        using updateApp.

        Example apps configuration:
            {
                "skylr": { "cpus": 0.3, "mem": 16, "instances": 3 },
                "extension": { "cpus": 0.2, "mem": 512, "instances": 3 },
                "scannr": { "cpus": 0.5, "mem": 128, "instances": 1 }
            }
        """
        for appId, newConfig in config.iteritems():
            self.updateApp(appId, newConfig)

def main():
    system = ServiceOrchestrator ('/etc/haproxy/conf.json')
    print system.gen ()

if __name__ == '__main__':
    #app.run()
    main()
