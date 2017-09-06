# ============LICENSE_START=======================================================
# org.onap.dcae
# ================================================================================
# Copyright (c) 2017 AT&T Intellectual Property. All rights reserved.
# ================================================================================
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#      http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.
# ============LICENSE_END=========================================================
#
# ECOMP is a trademark and service mark of AT&T Intellectual Property.

# Lifecycle interface calls for DockerContainer

import json, time, copy, random
from cloudify import ctx
from cloudify.decorators import operation
from cloudify.exceptions import NonRecoverableError, RecoverableError
import dockering as doc
from dockerplugin import discovery as dis
from dockerplugin.decorators import monkeypatch_loggers, wrap_error_handling_start, \
    merge_inputs_for_start
from dockerplugin.exceptions import DockerPluginDeploymentError, \
    DockerPluginDependencyNotReadyError
from dockerplugin import utils

# TODO: Remove this Docker port hardcoding and query for this port instead
DOCKER_PORT = 2376
# Always use the local Consul agent for interfacing with Consul from the plugin.
# Safe to assume that its always there.
CONSUL_HOST = "localhost"

# Used to construct delivery urls for data router subscribers. Data router in FTL
# requires https but this author believes that ONAP is to be defaulted to http.
DEFAULT_SCHEME = "http"

# Property keys
SERVICE_COMPONENT_NAME = "service_component_name"
SELECTED_CONTAINER_DESTINATION = "selected_container_destination"
CONTAINER_ID = "container_id"

# Lifecycle interface calls for dcae.nodes.DockerContainer

def _setup_for_discovery(**kwargs):
    """Setup for config discovery"""
    try:
        name = kwargs['name']
        application_config = kwargs['application_config']

        # NOTE: application_config is no longer a json string and is inputed as a
        # YAML map which translates to a dict. We don't have to do any
        # preprocessing anymore.
        conn = dis.create_kv_conn(CONSUL_HOST)
        dis.push_service_component_config(conn, name, application_config)
        return kwargs
    except dis.DiscoveryConnectionError as e:
        raise RecoverableError(e)
    except Exception as e:
        ctx.logger.error("Unexpected error while pushing configuration: {0}"
                .format(str(e)))
        raise NonRecoverableError(e)

def _generate_component_name(**kwargs):
    """Generate component name"""
    service_component_type = kwargs['service_component_type']
    name_override = kwargs['service_component_name_override']

    kwargs['name'] = name_override if name_override \
            else dis.generate_service_component_name(service_component_type)
    return kwargs

def _done_for_create(**kwargs):
    """Wrap up create operation"""
    name = kwargs['name']
    kwargs[SERVICE_COMPONENT_NAME] = name
    # All updates to the runtime_properties happens here. I don't see a reason
    # why we shouldn't do this because the context is not being mutated by
    # something else and will keep the other functions pure (pure in the sense
    # not dealing with CloudifyContext).
    ctx.instance.runtime_properties.update(kwargs)
    ctx.logger.info("Done setting up: {0}".format(name))
    return kwargs


@monkeypatch_loggers
@operation
def create_for_components(**kwargs):
    """Create step for Docker containers that are components

    This interface is responible for:

    1. Generating service component name
    2. Populating config information into Consul
    """
    _done_for_create(
            **_setup_for_discovery(
                **_generate_component_name(
                    **ctx.node.properties)))


def _parse_streams(**kwargs):
    """Parse streams and setup for DMaaP plugin"""
    # The DMaaP plugin requires this plugin to set the runtime properties
    # keyed by the node name.
    def setup_publishes(s):
        kwargs[s["name"]] = s

    map(setup_publishes, kwargs["streams_publishes"])

    def setup_subscribes(s):
        if s["type"] == "data_router":
            # If username and password has been provided then generate it. The
            # DMaaP plugin doesn't generate for subscribers. The generation code
            # and length of username password has been lifted from the DMaaP
            # plugin.

            # Don't want to mutate the source
            s = copy.deepcopy(s)
            if not s.get("username", None):
                s["username"] = utils.random_string(8)
            if not s.get("password", None):
                s["password"] = utils.random_string(10)

        kwargs[s["name"]] = s

    # NOTE: That the delivery url is constructed and setup in the start operation
    map(setup_subscribes, kwargs["streams_subscribes"])

    return kwargs

def _setup_for_discovery_streams(**kwargs):
    """Setup for discovery of streams

    Specifically, there's a race condition this call addresses for data router
    subscriber case. The component needs its feed subscriber information but the
    DMaaP plugin doesn't provide this until after the docker plugin start
    operation.
    """
    dr_subs = [kwargs[s["name"]] for s in kwargs["streams_subscribes"] \
            if s["type"] == "data_router"]

    if dr_subs:
        dmaap_kv_key = "{0}:dmaap".format(kwargs["name"])
        conn = dis.create_kv_conn(CONSUL_HOST)

        def add_feed(dr_sub):
            # delivery url and subscriber id will be fill by the dmaap plugin later
            v = { "location": dr_sub["location"], "delivery_url": None,
                    "username": dr_sub["username"], "password": dr_sub["password"],
                    "subscriber_id": None }
            return dis.add_to_entry(conn, dmaap_kv_key, dr_sub["name"], v) != None

        try:
            if all(map(add_feed, dr_subs)):
                return kwargs
        except Exception as e:
            raise NonRecoverableError(e)

        # You should never get here
        raise NonRecoverableError("Failure updating feed streams in Consul")
    else:
        return kwargs


@monkeypatch_loggers
@operation
def create_for_components_with_streams(**kwargs):
    """Create step for Docker containers that are components that use DMaaP

    This interface is responible for:

    1. Generating service component name
    2. Setup runtime properties for DMaaP plugin
    3. Populating application config into Consul
    4. Populating DMaaP config for data router subscribers in Consul
    """
    _done_for_create(
            **_setup_for_discovery(
                **_setup_for_discovery_streams(
                    **_parse_streams(
                        **_generate_component_name(
                            **ctx.node.properties)))))


@monkeypatch_loggers
@operation
def create_for_platforms(**kwargs):
    """Create step for Docker containers that are platform components

    This interface is responible for:

    1. Populating config information into Consul
    """
    _done_for_create(
            **_setup_for_discovery(
                **ctx.node.properties))


def _lookup_service(service_component_name, consul_host=CONSUL_HOST,
        with_port=False):
    conn = dis.create_kv_conn(consul_host)
    results = dis.lookup_service(conn, service_component_name)

    if with_port:
        # Just grab first
        result = results[0]
        return "{address}:{port}".format(address=result["ServiceAddress"],
                port=result["ServicePort"])
    else:
        return results[0]["ServiceAddress"]


def _verify_container(service_component_name, max_wait, consul_host=CONSUL_HOST):
    """Verify that the container is healthy

    Args:
    -----
    max_wait (integer): limit to how may attempts to make which translates to
        seconds because each sleep is one second. 0 means infinite.

    Return:
    -------
    True if component is healthy else a DockerPluginDeploymentError exception
    will be raised.
    """
    num_attempts = 1

    while True:
        if dis.is_healthy(consul_host, service_component_name):
            return True
        else:
            num_attempts += 1

            if max_wait > 0 and max_wait < num_attempts:
                raise DockerPluginDeploymentError("Container never became healthy")

            time.sleep(1)


def _create_and_start_container(container_name, image, docker_host,
        consul_host=CONSUL_HOST, **kwargs):
    """Create and start Docker container

    This is the function that actually does more of the heavy lifting including
    resolving the docker host to connect and common things to do in setting up
    docker containers like making sure CONSUL_HOST gets set as the local docker
    host ip.

    This method raises DockerPluginDependencyNotReadyError
    """
    try:
        # Setup for Docker operations

        docker_host_ip = _lookup_service(docker_host, consul_host=consul_host)

        client = doc.create_client(docker_host_ip, DOCKER_PORT)

        hcp = doc.add_host_config_params_volumes(volumes=kwargs.get("volumes",
            None))
        hcp = doc.add_host_config_params_ports(ports=kwargs.get("ports", None),
                host_config_params=hcp)
        hcp = doc.add_host_config_params_dns(docker_host_ip,
                host_config_params=hcp)

        # NOTE: The critical env variable CONSUL_HOST is being assigned the
        # docker host ip itself because there should be a local Consul agent. We
        # want services to register with their local Consul agent.
        # CONFIG_BINDING_SERVICE is here for backwards compatibility. This is a
        # well-known name now.
        platform_envs = { "CONSUL_HOST": docker_host_ip,
                "CONFIG_BINDING_SERVICE": "config_binding_service" }
        # NOTE: The order of the envs being passed in is **important**. The
        # kwargs["envs"] getting passed in last ensures that manual overrides
        # will override the hardcoded envs.
        envs = doc.create_envs(container_name, platform_envs, kwargs.get("envs", {}))

        # Do Docker operations

        container = doc.create_container(client, image, container_name, envs, hcp)
        container_id = doc.start_container(client, container)

        return container_id
    except (doc.DockerConnectionError, dis.DiscoveryConnectionError,
            dis.DiscoveryServiceNotFoundError) as e:
        raise DockerPluginDependencyNotReadyError(e)


def _parse_cloudify_context(**kwargs):
    """Parse Cloudify context

    Extract what is needed. This is impure function because it requires ctx.
    """
    kwargs["deployment_id"] = ctx.deployment.id
    return kwargs

def _enhance_docker_params(**kwargs):
    """Setup Docker envs"""
    docker_config = kwargs.get("docker_config", {})

    envs = kwargs.get("envs", {})
    # NOTE: Healthchecks are optional until prepared to handle use cases that
    # don't necessarily use http
    envs_healthcheck = doc.create_envs_healthcheck(docker_config) \
            if "healthcheck" in docker_config else {}
    envs.update(envs_healthcheck)

    # Set tags on this component for its Consul registration as a service
    tags = [kwargs.get("deployment_id", None), kwargs["service_id"]]
    tags = [ str(tag) for tag in tags if tag is not None ]
    # Registrator will use this to register this component with tags. Must be
    # comma delimited.
    envs["SERVICE_TAGS"] = ",".join(tags)

    kwargs["envs"] = envs

    def combine_params(key, docker_config, kwargs):
        v = docker_config.get(key, []) + kwargs.get(key, [])
        if v:
            kwargs[key] = v
        return kwargs

    # Add the lists of ports and volumes unintelligently - meaning just add the
    # lists together with no deduping.
    kwargs = combine_params("ports", docker_config, kwargs)
    kwargs = combine_params("volumes", docker_config, kwargs)

    return kwargs

def _create_and_start_component(**kwargs):
    """Create and start component (container)"""
    image = kwargs["image"]
    service_component_name = kwargs[SERVICE_COMPONENT_NAME]
    docker_host = kwargs[SELECTED_CONTAINER_DESTINATION]
    # Need to be picky and manually select out pieces because just using kwargs
    # which contains everything confused the execution of
    # _create_and_start_container because duplicate variables exist
    sub_kwargs = { "volumes": kwargs.get("volumes", []),
            "ports": kwargs.get("ports", None), "envs": kwargs.get("envs", {}) }

    container_id = _create_and_start_container(service_component_name, image,
            docker_host, **sub_kwargs)
    kwargs[CONTAINER_ID] = container_id

    # TODO: Use regular logging here
    ctx.logger.info("Container started: {0}, {1}".format(container_id,
        service_component_name))

    return kwargs

def _verify_component(**kwargs):
    """Verify component (container) is healthy"""
    service_component_name = kwargs[SERVICE_COMPONENT_NAME]
    # TODO: "Consul doesn't make its first health check immediately upon registration.
    # Instead it waits for the health check interval to pass."
    # Possible enhancement is to read the interval (and possibly the timeout) from
    # docker_config and multiply that by a number to come up with a more suitable
    # max_wait.
    max_wait = kwargs.get("max_wait", 300)

    # Verify that the container is healthy

    if _verify_container(service_component_name, max_wait):
        container_id = kwargs[CONTAINER_ID]
        service_component_name = kwargs[SERVICE_COMPONENT_NAME]

        # TODO: Use regular logging here
        ctx.logger.info("Container is healthy: {0}, {1}".format(container_id,
            service_component_name))

    return kwargs

def _done_for_start(**kwargs):
    ctx.instance.runtime_properties.update(kwargs)
    ctx.logger.info("Done starting: {0}".format(kwargs["name"]))
    return kwargs

@wrap_error_handling_start
@merge_inputs_for_start
@monkeypatch_loggers
@operation
def create_and_start_container_for_components(**start_inputs):
    """Create Docker container and start for components

    This operation method is to be used with the DockerContainerForComponents
    node type. After launching the container, the plugin will verify with Consul
    that the app is up and healthy before terminating.
    """
    _done_for_start(
            **_verify_component(
                **_create_and_start_component(
                    **_enhance_docker_params(
                        **_parse_cloudify_context(**start_inputs)))))


def _update_delivery_url(**kwargs):
    """Update the delivery url for data router subscribers"""
    dr_subs = [kwargs[s["name"]] for s in kwargs["streams_subscribes"] \
            if s["type"] == "data_router"]

    if dr_subs:
        service_component_name = kwargs[SERVICE_COMPONENT_NAME]
        # TODO: Should NOT be setting up the delivery url with ip addresses
        # because in the https case, this will not work because data router does
        # a certificate validation using the fqdn.
        subscriber_host = _lookup_service(service_component_name, with_port=True)

        for dr_sub in dr_subs:
            scheme = dr_sub["scheme"] if "scheme" in dr_sub else DEFAULT_SCHEME
            path = dr_sub["route"]
            dr_sub["delivery_url"] = "{scheme}://{host}/{path}".format(
                    scheme=scheme, host=subscriber_host, path=path)
            kwargs[dr_sub["name"]] = dr_sub

    return kwargs

@wrap_error_handling_start
@merge_inputs_for_start
@monkeypatch_loggers
@operation
def create_and_start_container_for_components_with_streams(**start_inputs):
    """Create Docker container and start for components that have streams

    This operation method is to be used with the DockerContainerForComponents
    node type. After launching the container, the plugin will verify with Consul
    that the app is up and healthy before terminating.
    """
    _done_for_start(
            **_update_delivery_url(
                **_verify_component(
                    **_create_and_start_component(
                        **_enhance_docker_params(
                            **_parse_cloudify_context(**start_inputs))))))


@wrap_error_handling_start
@monkeypatch_loggers
@operation
def create_and_start_container_for_platforms(**kwargs):
    """Create Docker container and start for platform services

    This operation method is to be used with the DockerContainerForPlatforms
    node type. After launching the container, the plugin will verify with Consul
    that the app is up and healthy before terminating.
    """
    image = ctx.node.properties["image"]
    docker_config = ctx.node.properties.get("docker_config", {})
    service_component_name = ctx.node.properties["name"]

    docker_host = ctx.instance.runtime_properties[SELECTED_CONTAINER_DESTINATION]

    envs = kwargs.get("envs", {})
    # NOTE: Healthchecks are optional until prepared to handle use cases that
    # don't necessarily use http
    envs_healthcheck = doc.create_envs_healthcheck(docker_config) \
            if "healthcheck" in docker_config else {}
    envs.update(envs_healthcheck)
    kwargs["envs"] = envs

    host_port = ctx.node.properties["host_port"]
    container_port = ctx.node.properties["container_port"]

    # Cloudify properties are all required and Cloudify complains that None
    # is not a valid type for integer. Defaulting to 0 to indicate to not
    # use this and not to set a specific port mapping in cases like service
    # change handler.
    if host_port != 0 and container_port != 0:
        # Doing this because other nodes might want to use this property
        port_mapping = "{cp}:{hp}".format(cp=container_port, hp=host_port)
        ports = kwargs.get("ports", []) + [ port_mapping ]
        kwargs["ports"] = ports
    if "ports" not in kwargs:
        ctx.logger.warn("No port mappings defined. Will randomly assign port.")

    container_id = _create_and_start_container(service_component_name, image,
            docker_host, **kwargs)
    ctx.instance.runtime_properties[CONTAINER_ID] = container_id

    ctx.logger.info("Container started: {0}, {1}".format(container_id,
        service_component_name))

    # Verify that the container is healthy

    max_wait = kwargs.get("max_wait", 300)

    if _verify_container(service_component_name, max_wait):
        ctx.logger.info("Container is healthy: {0}, {1}".format(container_id,
            service_component_name))


@wrap_error_handling_start
@monkeypatch_loggers
@operation
def create_and_start_container(**kwargs):
    """Create Docker container and start"""
    service_component_name = ctx.node.properties["name"]
    ctx.instance.runtime_properties[SERVICE_COMPONENT_NAME] = service_component_name

    image = ctx.node.properties["image"]
    docker_host = ctx.instance.runtime_properties[SELECTED_CONTAINER_DESTINATION]

    container_id = _create_and_start_container(service_component_name, image,
            docker_host, **kwargs)
    ctx.instance.runtime_properties[CONTAINER_ID] = container_id

    ctx.logger.info("Container started: {0}, {1}".format(container_id,
        service_component_name))


@monkeypatch_loggers
@operation
def stop_and_remove_container(**kwargs):
    """Stop and remove Docker container"""
    try:
        docker_host = ctx.instance.runtime_properties[SELECTED_CONTAINER_DESTINATION]

        docker_host_ip = _lookup_service(docker_host)

        client = doc.create_client(docker_host_ip, DOCKER_PORT)

        container_id = ctx.instance.runtime_properties[CONTAINER_ID]
        doc.stop_then_remove_container(client, container_id)

        cleanup_image = kwargs.get("cleanup_image", False)

        if cleanup_image:
            image = ctx.node.properties["image"]

            if doc.remove_image(client, image):
                ctx.logger.info("Removed Docker image: {0}".format(image))
            else:
                ctx.logger.warn("Couldnot remove Docker image: {0}".format(image))
    except (doc.DockerConnectionError, dis.DiscoveryConnectionError,
            dis.DiscoveryServiceNotFoundError) as e:
        raise RecoverableError(e)
    except Exception as e:
        ctx.logger.error("Unexpected error while stopping container: {0}"
                .format(str(e)))
        raise NonRecoverableError(e)

@monkeypatch_loggers
@operation
def cleanup_discovery(**kwargs):
    """Delete configuration from Consul"""
    service_component_name = ctx.instance.runtime_properties[SERVICE_COMPONENT_NAME]

    try:
        conn = dis.create_kv_conn(CONSUL_HOST)
        dis.remove_service_component_config(conn, service_component_name)
    except dis.DiscoveryConnectionError as e:
        raise RecoverableError(e)


# Lifecycle interface calls for dcae.nodes.DockerHost


@monkeypatch_loggers
@operation
def select_docker_host(**kwargs):
    selected_docker_host = ctx.node.properties['docker_host_override']
    name_search = ctx.node.properties['name_search']
    location_id = ctx.node.properties['location_id']

    if selected_docker_host:
        ctx.instance.runtime_properties[SERVICE_COMPONENT_NAME] = selected_docker_host
        ctx.logger.info("Selected Docker host: {0}".format(selected_docker_host))
    else:
        try:
            conn = dis.create_kv_conn(CONSUL_HOST)
            names = dis.search_services(conn, name_search, [location_id])
            ctx.logger.info("Docker hosts found: {0}".format(names))
            # Randomly choose one
            ctx.instance.runtime_properties[SERVICE_COMPONENT_NAME] = random.choice(names)
        except (dis.DiscoveryConnectionError, dis.DiscoveryServiceNotFoundError) as e:
            raise RecoverableError(e)
        except Exception as e:
            raise NonRecoverableError(e)

@operation
def unselect_docker_host(**kwargs):
    del ctx.instance.runtime_properties[SERVICE_COMPONENT_NAME]
    ctx.logger.info("Unselected Docker host")

