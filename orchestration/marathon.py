"""
A python module for making calls to **Marathon**.
"""

import json
import logging

import requests

logger = logging.getLogger('Marathon')
handler = logging.handlers.SysLogHandler(address='/dev/log', facility=19)
logger.addHandler(handler)

class Marathon(object):
    def __init__(self, url):
        self.url = url

    def getApps(self):
        """
        Calls the Marathon API that [lists all available apps.](https://mesosphere.github.io/marathon/docs/rest-api.html#get-/v2/apps)
        """
        url = "{0}/apps".format(self.url)
        req = requests.get(url, headers={'Accept': 'application/json'})

        return json.loads(req.content)['apps']

    def getTasks(self, appId):
        """
        Calls the Marathon API that [lists all running tasks for an application.](https://mesosphere.github.io/marathon/docs/rest-api.html#get-/v2/apps/%7Bappid%7D/tasks)
        """
        url = "{0}/apps/{1}/tasks".format(self.url, appId)
        req = requests.get(url, headers={'Accept': 'application/json'})

        return json.loads(req.content)['tasks']

    def updateApp(self, appId, newConfig):
        """
        Update the app with given appId using the new configuration

        Example:
            appId (string): "skylr"
            newConfig (dictionary): { "cpus": 0.3, "mem": 16, "instances": 3 }
        """
        logger.info('Attempting to update app [{0}] with new configuration: [{1}]'
            .format(appId, newConfig))

        url = "{0}/apps/{1}".format(self.url, appId)
        headers = {
            'Accept': 'application/json',
            'Content-Type': 'application/json'
        }
        req = requests.put(url, data=json.dumps(newConfig), headers=headers)

        print req.content

        return;
