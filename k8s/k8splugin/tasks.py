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

# Lifecycle interface calls for containerized components

# Needed by Cloudify Manager to load google.auth for the Kubernetes python client
import cloudify_importer

import time, copy
from cloudify import ctx
from cloudify.decorators import operation
from cloudify.exceptions import NonRecoverableError, RecoverableError
import dockering as doc
from onap_dcae_dcaepolicy_lib import Policies
from k8splugin import discovery as dis
from k8splugin.decorators import monkeypatch_loggers, wrap_error_handling_start, \
    merge_inputs_for_start, merge_inputs_for_create
from k8splugin.exceptions import DockerPluginDeploymentError
from k8splugin import utils
from configure import configure
from k8sclient import k8sclient

# Get configuration
plugin_conf = configure.configure()
CONSUL_HOST = plugin_conf.get("consul_host")
CONSUL_INTERNAL_NAME = plugin_conf.get("consul_dns_name")
DCAE_NAMESPACE = plugin_conf.get("namespace")

# Used to construct delivery urls for data router subscribers. Data router in FTL
# requires https but this author believes that ONAP is to be defaulted to http.
DEFAULT_SCHEME = "http"

# Property keys
SERVICE_COMPONENT_NAME = "service_component_name"
CONTAINER_ID = "container_id"
APPLICATION_CONFIG = "application_config"



# Utility methods

# Lifecycle interface calls for dcae.nodes.DockerContainer

def _setup_for_discovery(**kwargs):
    """Setup for config discovery"""
    try:
        name = kwargs['name']
        application_config = kwargs[APPLICATION_CONFIG]

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


@merge_inputs_for_create
@monkeypatch_loggers
@Policies.gather_policies_to_node()
@operation
def create_for_components(**create_inputs):
    """Create step for Docker containers that are components

    This interface is responsible for:

    1. Generating service component name
    2. Populating config information into Consul
    """
    _done_for_create(
            **_setup_for_discovery(
                **_generate_component_name(
                    **create_inputs)))


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


@merge_inputs_for_create
@monkeypatch_loggers
@Policies.gather_policies_to_node()
@operation
def create_for_components_with_streams(**create_inputs):
    """Create step for Docker containers that are components that use DMaaP

    This interface is responsible for:

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
                            **create_inputs)))))


@merge_inputs_for_create
@monkeypatch_loggers
@operation
def create_for_platforms(**create_inputs):
    """Create step for Docker containers that are platform components

    This interface is responible for:

    1. Populating config information into Consul
    """
    _done_for_create(
            **_setup_for_discovery(
                **create_inputs))


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


def _verify_container(service_component_name, max_wait):
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
        if k8sclient.is_available(DCAE_NAMESPACE, service_component_name):
            return True
        else:
            num_attempts += 1

            if max_wait > 0 and max_wait < num_attempts:
                raise DockerPluginDeploymentError("Container never became healthy")

            time.sleep(1)
  
    return True

def _create_and_start_container(container_name, image, **kwargs):
    '''
    This will create a k8s Deployment and, if needed, a k8s Service or two.
    (We are being opinionated in our use of k8s... this code decides what k8s abstractions and features to use.
    We're not exposing k8s to the component developer and the blueprint author.
    This is a conscious choice.  We want to use k8s in a controlled, consistent way, and we want to hide
    the details from the component developer and the blueprint author.)
    
    kwargs may have:
        - volumes:  array of volume objects, where a volume object is:
            {"host":{"path": "/path/on/host"}, "container":{"bind":"/path/on/container","mode":"rw_or_ro"}
        - ports: array of strings in the form "container_port:host_port"
        - env: map of name-value pairs ( {name0: value0, name1: value1...} )
        - always_pull: boolean.  If true, sets image pull policy to "Always"
          so that a fresh copy of the image is always pull.  Otherwise, sets
          image pull policy to "IfNotPresent"
        - msb_list: array of msb objects, where an msb object is as described in msb/msb.py.
        - log_info: an object with info for setting up ELK logging, with the form:
            {"log_directory": "/path/to/container/log/directory", "alternate_fb_path" : "/alternate/sidecar/log/path"}"
        - replicas: number of replicas to be launched initially
    '''
    env = { "CONSUL_HOST": CONSUL_INTERNAL_NAME,
            "CONFIG_BINDING_SERVICE": "config-binding-service" }
    env.update(kwargs.get("env", {}))
    ctx.logger.info("Deploying {}, image: {}, env: {}, kwargs: {}".format(container_name, image, env, kwargs))
    ctx.logger.info("Passing k8sconfig: {}".format(plugin_conf))
    replicas = kwargs.get("replicas", 1)
    _,dep = k8sclient.deploy(DCAE_NAMESPACE, 
                     container_name, 
                     image,
                     replicas = replicas, 
                     always_pull=kwargs.get("always_pull_image", False),
                     k8sconfig=plugin_conf,
                     volumes=kwargs.get("volumes",[]), 
                     ports=kwargs.get("ports",[]),
                     msb_list=kwargs.get("msb_list"), 
                     env = env,
                     labels = kwargs.get("labels", {}),
                     log_info=kwargs.get("log_info"))

    # Capture the result of deployment for future use 
    ctx.instance.runtime_properties["k8s_deployment"] = dep
    ctx.instance.runtime_properties["replicas"] = replicas
    ctx.logger.info ("Deployment complete: {0}".format(dep))

def _parse_cloudify_context(**kwargs):
    """Parse Cloudify context

    Extract what is needed. This is impure function because it requires ctx.
    """
    kwargs["deployment_id"] = ctx.deployment.id

    # Set some labels for the Kubernetes pods
    kwargs["labels"] = {
        "cfydeployment" : ctx.deployment.id,
        "cfynode": ctx.node.name,
        "cfynodeinstance": ctx.instance.id
    }

        # Pick up the centralized logging info
    if "log_info" in ctx.node.properties and "log_directory" in ctx.node.properties["log_info"]:
        kwargs["log_info"] = ctx.node.properties["log_info"]

    # Pick up replica count and always_pull_image flag
    if "replicas" in ctx.node.properties:
        kwargs["replicas"] = ctx.node.properties["replicas"]
    if "always_pull_image" in ctx.node.properties:
        kwargs["always_pull_image"] = ctx.node.properties["always_pull_image"]

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
    # Need to be picky and manually select out pieces because just using kwargs
    # which contains everything confused the execution of
    # _create_and_start_container because duplicate variables exist
    sub_kwargs = { 
        "volumes": kwargs.get("volumes", []),
        "ports": kwargs.get("ports", None),
        "envs": kwargs.get("envs", {}), 
        "log_info": kwargs.get("log_info", {}),
        "labels": kwargs.get("labels", {})}
    _create_and_start_container(service_component_name, image, **sub_kwargs)
   
    # TODO: Use regular logging here
    ctx.logger.info("Container started: {0}".format(service_component_name))

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
        service_component_name = kwargs[SERVICE_COMPONENT_NAME]

        # TODO: Use regular logging here
        ctx.logger.info("Container is healthy: {0}".format(service_component_name))
        
    return kwargs

def _done_for_start(**kwargs):
    ctx.instance.runtime_properties.update(kwargs)
    ctx.logger.info("Done starting: {0}".format(kwargs["name"]))
    return kwargs

def _setup_msb_registration(service_name, msb_reg):
    return {
        "serviceName" : service_name,
        "port" : msb_reg.get("port", "80"),
        "version" : msb_reg.get("version", "v1"),
        "url" : msb_reg.get("url_path", "/v1"),
        "protocol" : "REST",
        "enable_ssl" : msb_reg.get("uses_ssl", False),
        "visualRange" : "1"
}

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
            if "route" not in dr_sub:
                raise NonRecoverableError("'route' key missing from data router subscriber")
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

    This operation method is to be used with the ContainerizedPlatformComponent
    node type.
    """
    # Capture node properties
    image = ctx.node.properties["image"]
    docker_config = ctx.node.properties.get("docker_config", {})
    if "dns_name" in ctx.node.properties:
        service_component_name = ctx.node.properties["dns_name"]
    else:
        service_component_name = ctx.node.properties["name"]


    envs = kwargs.get("envs", {})
    # NOTE: Healthchecks are optional until prepared to handle use cases that
    # don't necessarily use http
    envs_healthcheck = doc.create_envs_healthcheck(docker_config) \
            if "healthcheck" in docker_config else {}
    envs.update(envs_healthcheck)
    kwargs["envs"] = envs

    # Set some labels for the Kubernetes pods
    kwargs["labels"] = {
        "cfydeployment" : ctx.deployment.id,
        "cfynode": ctx.node.name,
        "cfynodeinstance": ctx.instance.id
    }

    host_port = ctx.node.properties["host_port"]
    container_port = ctx.node.properties["container_port"]

    # Cloudify properties are all required and Cloudify complains that None
    # is not a valid type for integer. Defaulting to 0 to indicate to not
    # use this and not to set a specific port mapping in cases like service
    # change handler.
    if container_port != 0:
        # Doing this because other nodes might want to use this property
        port_mapping = "{cp}:{hp}".format(cp=container_port, hp=host_port)
        ports = kwargs.get("ports", []) + [ port_mapping ]
        kwargs["ports"] = ports
    if "ports" not in kwargs:
        ctx.logger.warn("No port mappings defined. Will randomly assign port.")

    # All of the new node properties could be handled more DRYly!
    # If a registration to MSB is required, then set up the registration info
    if "msb_registration" in ctx.node.properties and "port" in ctx.node.properties["msb_registration"]:
        kwargs["msb_list"] = [_setup_msb_registration(service_component_name, ctx.node.properties["msb_registration"])]

    # If centralized logging via ELK is desired, then set up the logging info
    if "log_info" in ctx.node.properties and "log_directory" in ctx.node.properties["log_info"]:
        kwargs["log_info"] = ctx.node.properties["log_info"]

    # Pick up replica count and always_pull_image flag
    if "replicas" in ctx.node.properties:
        kwargs["replicas"] = ctx.node.properties["replicas"]
    if "always_pull_image" in ctx.node.properties:
        kwargs["always_pull_image"] = ctx.node.properties["always_pull_image"]
    _create_and_start_container(service_component_name, image, **kwargs)

    ctx.logger.info("Container started: {0}".format(service_component_name))

    # Verify that the container is healthy

    max_wait = kwargs.get("max_wait", 300)

    if _verify_container(service_component_name, max_wait):
        ctx.logger.info("Container is healthy: {0}".format(service_component_name))


@wrap_error_handling_start
@monkeypatch_loggers
@operation
def create_and_start_container(**kwargs):
    """Create Docker container and start"""
    service_component_name = ctx.node.properties["name"]
    ctx.instance.runtime_properties[SERVICE_COMPONENT_NAME] = service_component_name

    image = ctx.node.properties["image"]

    _create_and_start_container(service_component_name, image,**kwargs)
    
    ctx.logger.info("Component deployed: {0}".format(service_component_name))


@monkeypatch_loggers
@operation
def stop_and_remove_container(**kwargs):
    """Stop and remove Docker container"""
    try:
        deployment_description = ctx.instance.runtime_properties["k8s_deployment"]
        k8sclient.undeploy(deployment_description)

    except Exception as e:
        ctx.logger.error("Unexpected error while stopping container: {0}"
                .format(str(e)))

@monkeypatch_loggers
@operation
def scale(replicas, **kwargs):
    """Change number of replicas in the deployment"""
    if replicas > 0:
        current_replicas = ctx.instance.runtime_properties["replicas"]
        ctx.logger.info("Scaling from {0} to {1}".format(current_replicas, replicas))
        try:
            deployment_description = ctx.instance.runtime_properties["k8s_deployment"]
            k8sclient.scale(deployment_description, replicas)
            ctx.instance.runtime_properties["replicas"] = replicas
        except Exception as e:
            ctx.logger.error ("Unexpected error while scaling {0}".format(str(e)))
    else:
        ctx.logger.info("Ignoring request to scale to zero replicas")
        
@monkeypatch_loggers
@Policies.cleanup_policies_on_node
@operation
def cleanup_discovery(**kwargs):
    """Delete configuration from Consul"""
    service_component_name = ctx.instance.runtime_properties[SERVICE_COMPONENT_NAME]

    try:
        conn = dis.create_kv_conn(CONSUL_HOST)
        dis.remove_service_component_config(conn, service_component_name)
    except dis.DiscoveryConnectionError as e:
        raise RecoverableError(e)


def _notify_container(**kwargs):
    """Notify container using the policy section in the docker_config"""
    dc = kwargs["docker_config"]

    if "policy" in dc:
        if dc["policy"]["trigger_type"] == "docker":
            pass
            """
            Need replacement for this in kubernetes.
            Need to find all the pods that have been deployed
            and execute the script in them.
            Kubernetes does not appear to have a way to ask for a script
            to be executed in all of the currently running pods for a
            Kubernetes Deployment or ReplicaSet.   We will have to find
            each of them and run the script.   The problem is that set of
            pods could be changing.   We can query to get all the pods, but
            there's no guarantee the list won't change while we're trying to
            execute the script.
            
            In ONAP R2, all of the policy-driven components rely on polling.
            """
            """
            # REVIEW: Need to finalize on the docker config policy data structure
            script_path = dc["policy"]["script_path"]
            updated_policies = kwargs["updated_policies"]
            removed_policies = kwargs["removed_policies"]
            policies = kwargs["policies"]
            cmd = doc.build_policy_update_cmd(script_path, use_sh=False,
                    msg_type="policies",
                    updated_policies=updated_policies,
                    removed_policies=removed_policies,
                    policies=policies
                    )

            docker_host = kwargs[SELECTED_CONTAINER_DESTINATION]
            docker_host_ip = _lookup_service(docker_host)
            logins = _get_docker_logins()
            client = doc.create_client(docker_host_ip, DOCKER_PORT, logins=logins)

            container_id = kwargs["container_id"]

            doc.notify_for_policy_update(client, container_id, cmd)
    """
    # else the default is no trigger

    return kwargs


@monkeypatch_loggers
@Policies.update_policies_on_node()
@operation
def policy_update(updated_policies, removed_policies=None, policies=None, **kwargs):
    """Policy update task

    This method is responsible for updating the application configuration and
    notifying the applications that the change has occurred. This is to be used
    for the dcae.interfaces.policy.policy_update operation.

    :updated_policies: contains the list of changed policy-configs when configs_only=True
        (default) Use configs_only=False to bring the full policy objects in :updated_policies:.
    """
    update_inputs = copy.deepcopy(ctx.instance.runtime_properties)
    update_inputs["updated_policies"] = updated_policies
    update_inputs["removed_policies"] = removed_policies
    update_inputs["policies"] = policies

    _notify_container(**update_inputs)
