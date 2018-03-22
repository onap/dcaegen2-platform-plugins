# ONAP DCAE Kubernetes Plugin for Cloudify

This directory contains a Cloudify plugin  used to orchestrate the deployment of containerized DCAE platform and service components  into a Kubernetes ("k8s") 
environment. This work is based on the [ONAP DCAE Docker plugin] (../docker).

This plugin is *not* a generic Kubernetes plugin that exposes the full set of Kubernetes features.
In fact, the plugin largely hides the fact that we're using Kubernetes from both component developers and blueprint authors,
The Cloudify node type definitions are very similar to the Cloudify type definitions used in the ONAP DCAE Docker plugin.

For the node types `ContainerizedPlatformComponent`, `ContainerizedServiceComponent`, and `ContainerizedServiceComponentUsingDmaap`, this plugin
creates the following Kubernetes entities:

- A Kubernetes `Deployment` containing information about what containers to run and what volume to mount.
  - The `Deployment` always includes a container that runs the component's Docker image
  - The `Deployment` includes any volumes specified in the blueprint
  - If the blueprint specifies a logging directory via the `log_info` property, the `Deployment` includes a second container,
  running the `filebeat` logging sidecar that ships logging information to the ONAP ELK stack.  The `Deployment` will include
  some additional volumes needed by filebeat.
- If the blueprint indicates that the component exposes any ports, the plugin will create a Kubernetes `Service` that allocates an address
  in the Kubernetes network address space that will route traffic to a container that's running the component.  This `Service` provides a 
  fixed "virtual IP" for the component.
- If the blueprint indicates that the component exposes a port externally, the plugin will create an additional Kubernetes `Service` that opens up a
  port on the external interface of each node in the Kubernetes cluster.

Through the `replicas` property, a blueprint can request deployment of multiple instances of the component.  The plugin will still create a single `Deployment` (and,
if needed one or two `Services`), but the `Deployment` will cause multiple instances of the container to run.   (Specifically, the `Deployment` will create
a Kubernetes `Pod` for each requested instance.)  Other entities connect to a component via the IP address of a `Service`, and Kubernetes takes care of routing 
traffic to an appropriate container instance.

## Pre-requisites
### Configuration
#### Configuration file
The plugin expects a configuration file in the Python "ini" format to be stored at `/opt/onap/config.txt`.  This file contains the address of the Consul cluster.
Here is an example:
```
[consul]
address=10.12.5.115:30270
```
#### Configuration entry in Consul
Additional configuration information is stored in the Consul KV store under the key `k8s-plugin`.
The configuration is provided as JSON object with the following properties:

    - namespace:  k8s namespace to use for DCAE
    - consul_dns_name: k8s internal DNS name for Consul (passed to containers)
    - image_pull_secrets: list of names of k8s secrets for accessing Docker registries, with the following properties:
    - filebeat:  object containing onfiguration for setting up filebeat container
            - log_path: mount point for log volume in filebeat container
            - data_path: mount point for data volume in filebeat container
            - config_path: mount point for config volume in filebeat container
            - config_subpath: subpath for config data in filebeat container
            - config_map: name of a ConfigMap holding the filebeat configuration file
            - image: Docker image to use for filebeat

#### Kubernetes access information
The plugin accesses a Kubernetes cluster.  The information and credentials for accessing a cluster are stored in a "kubeconfig" 
file.  The plugin expects to find such a file at `/etc/cloudify/.kube/config`.

#### Additional Kubernetes configuration elements
The plugin expects certain elements to be provided in the DCAE/ONAP environment, namely:
   - Kubernetes secret(s) containing the credentials needed to pull images from Docker registries, if needed
   - A Kubernetes ConfigMap containing the filebeat.yml file used by the filebeat logging container
   - An ExternalName service 


## Input parameters

### start

These input parameters are for the `start` `cloudify.interfaces.lifecycle` and are inputs into the variant task operations `create_and_start_container*`.

#### `envs`

A map of environment variables that is intended to be forwarded to the container as environment variables.  Example:

```yaml
envs:
  EXTERNAL_IP: '10.100.1.99'
```

These environment variables will be forwarded in addition to the *platform-related* environment variables like `CONSUL_HOST`.

#### `volumes`

List of maps used for setting up Kubernetes volume mounts.  Example:

```yaml
volumes:
  - host:
      path: '/var/run/docker.sock'
    container:
      bind: '/tmp/docker.sock'
      mode: 'ro'
```

The table below describes the fields.

key | description
--- | -----------
path | Full path to the file or directory on the host machine to be mounted
bind | Full path to the file or directory in the container where the volume should be mounted to
mode | Readable, writeable: `ro`, `rw`

#### `ports`

List of strings - Used to bind container ports to host ports. Each item is of the format: `<container port>:<host port>`.

Note that `ContainerizedPlatformComponent` has the property pair `host_port` and `container_port`. This pair will be merged with the input parameters ports.

```yaml
ports:
  - '8000:31000'
```

Default is `None`.

In the Kubernetes environment, most components will communicate over the Kubernetes network using private addresses. For those cases,
setting the `<host port>` to 0 will expose the `<container port>` to other components on the Kubernetes network, but not will not expose any
ports on the Kubernetes host's external interface.    Setting `<host port>` to a non-zero value will expose that port on the external interfaces
of every Kubernetes host in the cluster.  (This uses the Kubernetes `NodePort` service type.)

#### `max_wait`

Integer - seconds to wait for Docker to come up healthy before throwing a `NonRecoverableError`.

```yaml
max_wait:
    60
```

Default is 300 seconds.


## Using DMaaP

The node type `dcae.nodes.ContainerizedServiceComponentUsingDmaap` is intended to be used by components that use DMaaP and expects to be connected with the DMaaP node types found in the DMaaP plugin.

### Node properties

The properties `streams_publishes` and `streams_subscribes` both are lists of objects that are intended to be passed into the DMaaP plugin and used to create additional parameters that will be passed into the DMaaP plugin.

#### Message router

For message router publishers and subscribers, the objects look like:

```yaml
name: topic00
location: mtc5
client_role: XXXX
type: message_router
```

Where `name` is the node name of `dcae.nodes.Topic` or `dcae.nodes.ExistingTopic` that the Docker node is connecting with via the relationships `dcae.relationships.publish_events` for publishing and `dcae.relationships.subscribe_to_events` for subscribing.

#### Data router

For data router publishers, the object looks like:

```yaml
name: feed00
location: mtc5
type: data_router
```

Where `name` is the node name of `dcae.nodes.Feed` or `dcae.nodes.ExistingFeed` that the Docker node is connecting with via the relationships `dcae.relationships.publish_files`.

For data router subscribers, the object looks like:

```yaml
name: feed00
location: mtc5
type: data_router
username: king
password: "123456"
route: some-path
scheme: https
```

Where the relationship to use is `dcae.relationships.subscribe_to_files`.

If `username` and `password` are not provided, then the plugin will generate username and password pair.

`route` and `scheme` are parameter used in the dynamic construction of the delivery url which will be passed to the DMaaP plugin to be used in the setting up of the subscriber to the feed.

`route` is the http path endpoint of the subscriber that will handle files from the associated feed.

`scheme` is either `http` or `https`.  If not specified, then the plugin will default to `http`.

### Component configuration

The DMaaP plugin is responsible to provision the feed/topic and store into Consul the resulting DMaaP connection details.  Here is an example:

```json
{
    "topic00": {
        "client_role": "XXXX",
        "client_id": "XXXX",
        "location": "XXXX",
        "topic_url": "https://some-topic-url.com/events/abc"
    }
}
```

This is to be merged with the templatized application configuration:

```json
{
    "some-param": "Lorem ipsum dolor sit amet",
    "streams_subscribes": {
        "topic-alpha": {
            "type": "message_router",
            "aaf_username": "user-foo",
            "aaf_password": "password-bar",
            "dmaap_info": "<< topic00 >>"
        },
    },
    "streams_publishes": {},
    "services_calls": {}
}
```

To form the application configuration:

```json
{
    "some-param": "Lorem ipsum dolor sit amet",
    "streams_subscribes": {
        "topic-alpha": {
            "type": "message_router",
            "aaf_username": "user-foo",
            "aaf_password": "password-bar",
            "dmaap_info": {
                "client_role": "XXXX",
                "client_id": "XXXX",
                "location": "XXXX",
                "topic_url": "https://some-topic-url.com/events/abc"
            }
        },
    },
    "streams_publishes": {},
    "services_calls": {}
}
```

This also applies to data router feeds.
