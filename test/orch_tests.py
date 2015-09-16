#!/usr/bin/env python
"""
**Orchestration Test** is a simple suite of tests for the services. Tests are
run by the python coverage module.  Care was taken to make no alterations to
the file system during the execution of the tests, and not to execute any of
the commands that would normally attempt to restart HAProxy.

To be specific, these functions are mocked, and rather than executed, their
calling parameters are tested for an expected value.  For example, see the
test_marathon test.

To run (from the command line):

./bin/orch.sh test     # for basic tests

./bin/orch.sh cover    # for a coverage report

Notes:

 * The **@patch** decorator injects an instance of MagicMock, which inherits
  from the [Mock class](http://www.voidspace.org.uk/python/mock/mock.html#mock.Mock).
 * These patches inject their arguments in, "reverse," order - i.e. the top one is
  the last argument.
 * It's a good idea to **@patch** the subprocess.call() method for everything, just in
  case we do actually break something.

Future tests:

* Make test marathon update from appId that's not in the configuration.
* Test invalid host
"""

# Built-in imports
import json
import os
import sys
import unittest

# Installed imports
from mock import call, patch

# Hack to get test file in its own directory.
lib_path = os.path.join(os.path.dirname(__file__), '..')
sys.path.append(lib_path)

os.environ['CONFIG_FILE'] = './etc/test_config.json'
SKYLR_HOME = os.environ.get('SKYLR_HOME', '/mnt/skylr/app/skylr')

import main
from orchestration.ServiceOrchestrator import ServiceOrchestrator

# === ServiceTestCase ===
class ServiceTestCase(unittest.TestCase):
    """
    At present, this is the only test case we really need.
    """
    def setUp(self):
        main.app.config['TESTING'] = True
        self.app = main.app.test_client()
        self.configDest = "/tmp/haproxy.test.cfg"
        self.usersConfig = "/etc/haproxy/haproxy_users.cfg"
        self.pidFile = "/tmp/haproxy_test.pid"
        self.tmpConfig =  os.path.join(SKYLR_HOME, 'haproxy.cfg')

    def tearDown(self):
        pass

    @patch('orchestration.ServiceOrchestrator.ServiceOrchestrator.isApprovedHost')
    @patch('orchestration.ServiceOrchestrator.ServiceOrchestrator.writeTmpConfig')
    @patch('orchestration.marathon.Marathon.getTasks')
    @patch('orchestration.marathon.Marathon.getApps')
    @patch('subprocess.call')
    def test_marathon(self, subCall, getApps, getTasks, writeTmpConfig, isApprovedHost):
        """
        This test exercises pretty much the whole marathon service call, without
        writing anything to the filesystem, or restarting HAProxy.
        """
        # Set some mock return values
        getApps.return_value = sample_marathon_apps
        getTasks.return_value = sample_marathon_tasks
        isApprovedHost.return_value = True
        writeTmpConfig.return_value = self.tmpConfig

        # Build some mock calls to subprocess.call() (which usually copies
        # files and restarts HAProxy)
        command1 = "cp {0} {1}".format(self.tmpConfig, self.configDest)
        command2 = "haproxy -f {0} -f {1} -p {2} -D".format(
            self.configDest, self.usersConfig, self.pidFile)
        call_list = [call(command1.split(" ")), call(command2.split(" "))]

        # Call the Flask service at the '/marathon' endpoint.
        rv = self.app.post('/marathon', data=json.dumps({
            'taskId': 'Skylr_1-1410358994130',
            'taskStatus': 1,
            'appID': 'skylr',
            'host': 'c4.skylr.renci.org',
            'ports': [ 31351 ],
            'eventType': 'status_update_event'
        }))

        # Assertions
        self.assertEqual(rv.data, 'True')
        writeTmpConfig.assert_called_once_with(sample_config_text)
        subCall.assert_has_calls(call_list)

    @patch('orchestration.ServiceOrchestrator.ServiceOrchestrator.reloadHAProxy')
    @patch('subprocess.call')
    def test_marathon2(self, subCall, reloadHAProxy):
        """
        This test makes sure the endpoint itself doesn't make any call
        to the backend when the POST data doesn't match what we're looking
        for in a Marathon update.
        """
        rv = self.app.post('/marathon', data=json.dumps({
            'clientIp': '152.54.2.52',
            'uri': '/v2/apps/Skylr',
            'appDefinition': {
                'id': 'Skylr',
                'env': {},
                'instances': 2,
                'cpus': 0.1,
                'mem': 16,
                'executor': '',
                'constraints': [],
                'uris': [],
                'ports': [ 15868 ],
                'taskRateLimit': 1,
                'tasks': [] },
            'eventType': 'api_post_event'
        }))

        # Assertions
        self.assertEqual(rv.data, 'not status_update_event')
        assert not reloadHAProxy.called
        assert not subCall.called

    @patch('orchestration.marathon.Marathon.updateApp')
    def test_updateApp(self, updateApp):
        """
        Exercises the updateApp endpoint.  Note, "scannr" is not in the
        test_config.json file, so it will not be in any of the calls.
        """
        update = {
            "skylr": { "cpus": 0.3, "mem": 16, "instances": 3 },
            "extension": { "cpus": 0.2, "mem": 512, "instances": 3 },
            "scannr": { "cpus": 0.5, "mem": 128, "instances": 1 }
        }
        call1 = call("skylr", update["skylr"])
        call2 = call("extension", update["extension"])

        rv = self.app.post('/updateApp', data=json.dumps(update))

        # Assertions
        self.assertEqual(rv.data, 'ok')
        self.assertEqual(updateApp.call_count, 2)
        updateApp.assert_has_calls([call1, call2], any_order=True)


# === Test Case Support Variables ===
sample_marathon_apps = [ {
    'id': "skylr",
    'cmd': "/mnt/skylr/app/skylr/bin/skylr-mesos.sh run_oscar",
    'env': { },
    'instances': 5,
    'cpus': 0.1,
    'mem': 16,
    'disk': 0,
    'executor': "",
    'constraints': [ ],
    'uris': [ ],
    'ports': [
        3000
    ],
    'taskRateLimit': 1,
    'container': None,
    'healthChecks': [ ],
    'version': "2014-10-07T19:30:08.080Z",
    'tasksStaged': 0,
    'tasksRunning': 5 }
]

sample_marathon_tasks = [
    {
        'id': "skylr.03a2b8d7-53b1-11e4-8ac2-525400700df7",
        'host': "10.17.1.15",
        'ports': [
            31443
        ],
        'startedAt': "2014-10-14T14:47:27.445Z",
        'stagedAt': "2014-10-14T14:47:26.327Z",
        'version': "2014-10-07T19:30:08.080Z"
    },
    {
        'id': "skylr.673817e0-4adb-11e4-9bc6-525400700df7",
        'host': "10.17.1.16",
        'ports': [
            31290
        ],
        'startedAt': "2014-10-03T08:58:11.948Z",
        'stagedAt': "2014-10-03T08:58:11.798Z",
        'version': "2014-10-02T21:16:11.959Z"
    }
]

sample_config_text = """
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

frontend http-in-skylr
    bind :4000
    reqadd X-Forwarded-Proto:\ https
    acl is_websocket hdr(Connection)  -i Upgrade
    acl is_websocket path_beg /socket.io
    acl is_websocket hdr(Upgrade) -i WebSocket
    use_backend websocket-skylr if is_websocket #is_connection
    default_backend www-skylr
backend www-skylr
    timeout server 30s
    balance roundrobin
    option httpclose
    option http-server-close
    acl auth_ok http_auth(site_users)
    http-request auth unless auth_ok

    server service-app-0 10.17.1.15:31443
    server service-app-1 10.17.1.16:31290
backend websocket-skylr
    mode http
    balance leastconn
    timeout server 600s
    option forwardfor
    option http-server-close
    option forceclose
    no option httpclose
    cookie WEBSOCKETSERV insert indirect nocache preserve
    appsession WEBSOCKETSERV len 52 timeout 3h request-learn
    server service-app-0 10.17.1.15:31443 cookie service-app-0 weight 1 maxconn 8192 check
    server service-app-1 10.17.1.16:31290 cookie service-app-1 weight 1 maxconn 8192 check


"""

if __name__ == '__main__':
    unittest.main()
