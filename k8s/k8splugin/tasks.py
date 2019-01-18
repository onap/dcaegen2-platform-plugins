# ============LICENSE_START=======================================================
# org.onap.dcae
# ================================================================================
# Copyright (c) 2017-2018 AT&T Intellectual Property. All rights reserved.
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
import json
from cloudify import ctx
from cloudify.decorators import operation
from cloudify.exceptions import NonRecoverableError, RecoverableError
from onap_dcae_dcaepolicy_lib import Policies
from k8splugin import discovery as dis
from k8splugin.decorators import monkeypatch_loggers, wrap_error_handling_start, \
    merge_inputs_for_start, merge_inputs_for_create, wrap_error_handling_update
from k8splugin.exceptions import DockerPluginDeploymentError
from k8splugin import utils
from configure import configure
import k8sclient

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
K8S_DEPLOYMENT = "k8s_deployment"

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
    """Create step for service components

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
    """Create step for service components that use DMaaP

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
    """Create step for platform components

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


def _verify_k8s_deployment(service_component_name, max_wait):
    """Verify that the k8s Deployment is ready

    Args:
    -----
    max_wait (integer): limit to how may attempts to make which translates to
        seconds because each sleep is one second. 0 means infinite.

    Return:
    -------
    True if deployment is ready else a DockerPluginDeploymentError exception
    will be raised.
    """
    num_attempts = 1

    while True:
        if k8sclient.is_available(DCAE_NAMESPACE, service_component_name):
            return True
        else:
            num_attempts += 1

            if max_wait > 0 and max_wait < num_attempts:
                raise DockerPluginDeploymentError("k8s deployment never became ready for {0}".format(service_component_name))

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
        - envs: map of name-value pairs ( {name0: value0, name1: value1...} )
        - always_pull: boolean.  If true, sets image pull policy to "Always"
          so that a fresh copy of the image is always pull.  Otherwise, sets
          image pull policy to "IfNotPresent"
        - msb_list: array of msb objects, where an msb object is as described in msb/msb.py.
        - log_info: an object with info for setting up ELK logging, with the form:
            {"log_directory": "/path/to/container/log/directory", "alternate_fb_path" : "/alternate/sidecar/log/path"}"
        - replicas: number of replicas to be launched initially
        - readiness: object with information needed to create a readiness check
    '''
    env = { "CONSUL_HOST": CONSUL_INTERNAL_NAME,
            "CONFIG_BINDING_SERVICE": "config-binding-service" }
    env.update(kwargs.get("envs", {}))
    ctx.logger.info("Starting k8s deployment for {}, image: {}, env: {}, kwargs: {}".format(container_name, image, env, kwargs))
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
                     tls_info=kwargs.get("tls_info"),
                     env = env,
                     labels = kwargs.get("labels", {}),
                     log_info=kwargs.get("log_info"),
                     readiness=kwargs.get("readiness"))

    # Capture the result of deployment for future use
    ctx.instance.runtime_properties[K8S_DEPLOYMENT] = dep
    ctx.instance.runtime_properties["replicas"] = replicas
    ctx.logger.info ("k8s deployment initiated successfully for {0}: {1}".format(container_name, dep))

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

    # Pick up TLS info if present
    if "tls_info" in ctx.node.properties:
        kwargs["tls_info"] = ctx.node.properties["tls_info"]

    # Pick up replica count and always_pull_image flag
    if "replicas" in ctx.node.properties:
        kwargs["replicas"] = ctx.node.properties["replicas"]
    if "always_pull_image" in ctx.node.properties:
        kwargs["always_pull_image"] = ctx.node.properties["always_pull_image"]

    return kwargs

def _enhance_docker_params(**kwargs):
    '''
    Set up Docker environment variables and readiness check info
    and inject into kwargs.
    '''

    # Get info for setting up readiness probe, if present
    docker_config = kwargs.get("docker_config", {})
    if "healthcheck" in docker_config:
        kwargs["readiness"] = docker_config["healthcheck"]

    envs = kwargs.get("envs", {})

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
        "tls_info": kwargs.get("tls_info", {}),
        "labels": kwargs.get("labels", {}),
        "readiness": kwargs.get("readiness",{})}
    _create_and_start_container(service_component_name, image, **sub_kwargs)

    return kwargs

def _verify_component(**kwargs):
    """Verify deployment is ready"""
    service_component_name = kwargs[SERVICE_COMPONENT_NAME]

    max_wait = kwargs.get("max_wait", 300)
    ctx.logger.info("Waiting up to {0} secs for {1} to become ready".format(max_wait, service_component_name))

    if _verify_k8s_deployment(service_component_name, max_wait):
        ctx.logger.info("k8s deployment is ready for: {0}".format(service_component_name))

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
    """Initiate Kubernetes deployment for service components

    This operation method is to be used with the ContainerizedServiceComponent
    node type. After initiating a Kubernetes deployment, the plugin will verify with Kubernetes
    that the app is up and responding successfully to readiness probes.
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
    """Initiate Kubernetes deployment for service components that have streams

    This operation method is to be used with the ContainerizedServiceComponentUsingDmaap
    node type. After initiating the Kubernetes deployment, the plugin will verify with
    Kubernetes that the app is up and responding successfully to readiness probes.
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
    """Initiate Kubernetes deployment for platform components

    This operation method is to be used with the ContainerizedPlatformComponent
    node type.
    """
    # Capture node properties
    image = ctx.node.properties["image"]
    docker_config = ctx.node.properties.get("docker_config", {})
    if "healthcheck" in docker_config:
        kwargs["readiness"] = docker_config["healthcheck"]
    if "dns_name" in ctx.node.properties:
        service_component_name = ctx.node.properties["dns_name"]
    else:
        service_component_name = ctx.node.properties["name"]

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

    # Pick up TLS info if present
    if "tls_info" in ctx.node.properties:
        kwargs["tls_info"] = ctx.node.properties["tls_info"]

    # Pick up replica count and always_pull_image flag
    if "replicas" in ctx.node.properties:
        kwargs["replicas"] = ctx.node.properties["replicas"]
    if "always_pull_image" in ctx.node.properties:
        kwargs["always_pull_image"] = ctx.node.properties["always_pull_image"]
    _create_and_start_container(service_component_name, image, **kwargs)

    # Verify that the k8s deployment is ready

    max_wait = kwargs.get("max_wait", 300)
    ctx.logger.info("Waiting up to {0} secs for {1} to become ready".format(max_wait, service_component_name))

    if _verify_k8s_deployment(service_component_name, max_wait):
        ctx.logger.info("k8s deployment ready for: {0}".format(service_component_name))


@wrap_error_handling_start
@monkeypatch_loggers
@operation
def create_and_start_container(**kwargs):
    """Initiate a Kubernetes deployment for the generic ContainerizedApplication node type"""
    service_component_name = ctx.node.properties["name"]
    ctx.instance.runtime_properties[SERVICE_COMPONENT_NAME] = service_component_name

    image = ctx.node.properties["image"]

    _create_and_start_container(service_component_name, image,**kwargs)

@monkeypatch_loggers
@operation
def stop_and_remove_container(**kwargs):
    """Delete Kubernetes deployment"""
    if K8S_DEPLOYMENT in ctx.instance.runtime_properties:
        try:
            deployment_description = ctx.instance.runtime_properties[K8S_DEPLOYMENT]
            k8sclient.undeploy(deployment_description)

        except Exception as e:
            ctx.logger.error("Unexpected error while deleting k8s deployment: {0}"
                    .format(str(e)))
    else:
        # A previous install workflow may have failed,
        # and no Kubernetes deployment info was recorded in runtime_properties.
        # No need to run the undeploy operation
        ctx.logger.info("No k8s deployment information, not attempting to delete k8s deployment")

@wrap_error_handling_update
@monkeypatch_loggers
@operation
def scale(replicas, **kwargs):
    """Change number of replicas in the deployment"""
    service_component_name = ctx.instance.runtime_properties["service_component_name"]

    if replicas > 0:
        current_replicas = ctx.instance.runtime_properties["replicas"]
        ctx.logger.info("Scaling {0} from {1} to {2} replica(s)".format(service_component_name, current_replicas, replicas))
        deployment_description = ctx.instance.runtime_properties[K8S_DEPLOYMENT]
        k8sclient.scale(deployment_description, replicas)
        ctx.instance.runtime_properties["replicas"] = replicas

        # Verify that the scaling took place as expected
        max_wait = kwargs.get("max_wait", 300)
        ctx.logger.info("Waiting up to {0} secs for {1} to scale and become ready".format(max_wait, service_component_name))
        if _verify_k8s_deployment(service_component_name, max_wait):
            ctx.logger.info("Scaling complete: {0} from {1} to {2} replica(s)".format(service_component_name, current_replicas, replicas))

    else:
        ctx.logger.info("Ignoring request to scale {0} to zero replicas".format(service_component_name))

@wrap_error_handling_update
@monkeypatch_loggers
@operation
def update_image(image, **kwargs):
    """ Restart component with a new Docker image """

    service_component_name = ctx.instance.runtime_properties["service_component_name"]
    if image:
        current_image = ctx.instance.runtime_properties["image"]
        ctx.logger.info("Updating app image for {0} from {1} to {2}".format(service_component_name, current_image, image))
        deployment_description = ctx.instance.runtime_properties[K8S_DEPLOYMENT]
        k8sclient.upgrade(deployment_description, image)
        ctx.instance.runtime_properties["image"] = image

        # Verify that the update took place as expected
        max_wait = kwargs.get("max_wait", 300)
        ctx.logger.info("Waiting up to {0} secs for {1} to be updated and become ready".format(max_wait, service_component_name))
        if _verify_k8s_deployment(service_component_name, max_wait):
            ctx.logger.info("Update complete: {0} from {1} to {2}".format(service_component_name, current_image, image))

    else:
        ctx.logger.info("Ignoring update_image request for {0} with unusable image '{1}'".format(service_component_name, str(image)))

#TODO: implement rollback operation when kubernetes python client fix is available.
# (See comments in k8sclient.py.)
# In the meantime, it's possible to undo an update_image operation by doing a second
# update_image that specifies the older image.

@monkeypatch_loggers
@Policies.cleanup_policies_on_node
@operation
def cleanup_discovery(**kwargs):
    """Delete configuration from Consul"""
    if SERVICE_COMPONENT_NAME in ctx.instance.runtime_properties:
        service_component_name = ctx.instance.runtime_properties[SERVICE_COMPONENT_NAME]

        try:
            conn = dis.create_kv_conn(CONSUL_HOST)
            dis.remove_service_component_config(conn, service_component_name)
        except dis.DiscoveryConnectionError as e:
            raise RecoverableError(e)
    else:
        # When another node in the blueprint fails install,
        # this node may not have generated a service component name.
        # There's nothing to delete from Consul.
        ctx.logger.info ("No service_component_name, not attempting to delete config from Consul")

def _notify_container(**kwargs):
    """
    Notify container using the policy section in the docker_config.
    Notification consists of running a script in the application container
    in each pod in the Kubernetes deployment associated with this node.
    Return the list of notification results.
    """
    dc = kwargs["docker_config"]
    resp = []

    if "policy" in dc:
        if dc["policy"]["trigger_type"] == "docker":

             # Build the command to execute in the container
             # SCRIPT_PATH policies {"policies" : ...., "updated_policies" : ..., "removed_policies": ...}
            script_path = dc["policy"]["script_path"]
            policy_data = {
                "policies": kwargs["policies"],
                "updated_policies": kwargs["updated_policies"],
                "removed_policies": kwargs["removed_policies"]
            }

            command = [script_path, "policies", json.dumps(policy_data)]

            # Execute the command
            deployment_description = ctx.instance.runtime_properties[K8S_DEPLOYMENT]
            resp = k8sclient.execute_command_in_deployment(deployment_description, command)

    # else the default is no trigger

    return resp

@operation
@monkeypatch_loggers
@Policies.update_policies_on_node()
def policy_update(updated_policies, removed_policies=None, policies=None, **kwargs):
    """Policy update task

    This method is responsible for updating the application configuration and
    notifying the applications that the change has occurred. This is to be used
    for the dcae.interfaces.policy.policy_update operation.

    :updated_policies: contains the list of changed policy-configs when configs_only=True
        (default) Use configs_only=False to bring the full policy objects in :updated_policies:.
    """
    service_component_name = ctx.instance.runtime_properties[SERVICE_COMPONENT_NAME]
    ctx.logger.info("policy_update for {0}-- updated_policies: {1}, removed_policies: {2}, policies: {3}"
        .format(service_component_name, updated_policies, removed_policies, policies))
    update_inputs = copy.deepcopy(ctx.instance.runtime_properties)
    update_inputs["updated_policies"] = updated_policies
    update_inputs["removed_policies"] = removed_policies
    update_inputs["policies"] = policies

    resp = _notify_container(**update_inputs)
    ctx.logger.info("policy_update complete for {0}--notification results: {1}".format(service_component_name,json.dumps(resp)))