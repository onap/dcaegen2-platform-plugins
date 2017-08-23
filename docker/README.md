# docker-cloudify

This repository contains Cloudify artifacts used to orchestrate the deployment of Docker containers.  See the example blueprints in the [`examples` directory](examples).

More details about what is expected from Docker components can be found in the DCAE ONAP documentation.

## Input parameters

### start

These input parameters are for the `start` `cloudify.interfaces.lifecycle` and are inputs into the variant task operations `create_and_start_container*`.

#### `envs`

A map of environment variables that is intended to be forwarded to the Docker container as environment variables.  Example:

```yaml
envs:
  EXTERNAL_IP: '10.100.1.99'
```

These environment variables will be forwarded in addition to the *platform-related* environment variables like `CONSUL_HOST`.

#### `volumes`

List of maps used for setting up Docker volume mounts.  Example:

```yaml
volumes:
  - host:
      path: '/var/run/docker.sock'
    container:
      bind: '/tmp/docker.sock'
      mode: 'ro'
```

This information is used to pass forward into [`docker-py` create container call](http://docker-py.readthedocs.io/en/1.10.6/volumes.html).

key | description
--- | -----------
path | Full path to the file or directory on the host machine to be mounted
bind | Full path to the file or directory in the container where the volume should be mounted to
mode | Readable, writeable: `ro`, `rw`

#### `ports`

List of strings - Used to bind container ports to host ports. Each item is of the format: `<container port>:<host port>`.

Note that `DockerContainerForPlatforms` has the property pair `host_port` and `container_port`. This pair will be merged with the input parameters ports.

```yaml
ports:
  - '8000:8000'
```

Default is `None`.

#### `max_wait`

Integer - seconds to wait for Docker to come up healthy before throwing a `NonRecoverableError`.

```yaml
max_wait:
    60
```

Default is 300 seconds.

### stop

These input parameters are for the `stop` `cloudify.interfaces.lifecycle` and are inputs into the task operation `stop_and_remove_container`.

#### `cleanup_image`

Boolean that controls whether to attempt to remove the associated Docker image (true) or not (false).

```yaml
cleanup_image
    True
```

Default is false.

## Using DMaaP

The node type `dcae.nodes.DockerContainerForComponentsUsingDmaap` is intended to be used by components that use DMaaP and expects to be connected with the DMaaP node types found in the DMaaP plugin.

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

This is to be merged with the templetized application configuration:

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
