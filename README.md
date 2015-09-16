#Skylr Orchestration

##Overview

**Skylr Service Orchestrator** is a server that helps orchestrate instances
of jobs managed by our Marathon and Mesos cluster management installations.
It is primarily a [Flask](http://flask.pocoo.org/) server that listens for
several HTTP requests pertaining to Marathon job orchestration.  For example,
it listens for HTTP POST requests from the Marathon server itself that
advertise a "*service_update_event*".

It performs the following actions:
 * Receives update events in the form of HTTP POST requests from Marathon and rewrites an HAProxy configuration file based on the server locations of the new application instances.
 * Receives update events in the form of HTTP POST requests from an outside source and posts them to Marathon, to change the configuration for a job on Marathon.

##Installation
Clone the repository:
```
git clone git@github.com:LAS-NCSU/skylr-orchestration.git
```
Run the setup script to install all the required modules:
```
./bin/orch.sh setup
```
Run the server in development mode:
```
sudo -E ./bin/orch.sh run dev -c ./etc/local_config.json
```
Or run the server in production mode:
```
./bin/orch.sh run prod
```
Opening a firewall port on Fedora 20:
```
sudo firewall-cmd --zone=public --add-port --port=3000/tcp
```

##Testing

VirtualEnv must be activated for the unit testing script:
```
./bin/orch.sh activate_venv
./bin/orch.sh test
```

##Configuration

The configuration files in the */etc* directory contain a few variables that will
need to change based on your environment.

Sample configuration:
```
{
    "marathon_hosts" : [
        "c0.skylr.renci.org:8080"
    ],
    "services" : {
        "skylr" : {
            "port"     : 3000,
            "authConf" : "site_users"
        },
        "extension" : {
            "port" : 3002,
            "backend_port" : 3002
        },
        "chronos" : {
            "port" : 8001
        }
    },
    "config_destination": "/etc/haproxy/haproxy.auto.cfg",
    "users_config_destination": "/etc/haproxy/haproxy_users.cfg",
    "pid_file": "/var/run/haproxy.pid"
}
```
As you can see, the bottom 3 variables are file destinations, the first two of which
are locations where the HAProxy.

The *marathon_hosts* variable is used both to communicate to, and validate HTTP requests
from the Marathon server.

Each service can contain a number of number of configuration variables:
 * *authConf*: this will specify that we need basic authentication for the service.
 * *backend_port*: if the application will only have 1 port on a given server, use this variable
 * *port*: this is the port that HAPRoxy should listen on to direct traffic to the backend systems.
