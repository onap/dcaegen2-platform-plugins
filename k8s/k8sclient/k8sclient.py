# ============LICENSE_START=======================================================
# org.onap.dcae
# ================================================================================
# Copyright (c) 2018 AT&T Intellectual Property. All rights reserved.
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
import os
import re
import uuid
from msb import msb
from kubernetes import config, client, stream

# Default values for readiness probe
PROBE_DEFAULT_PERIOD = 15
PROBE_DEFAULT_TIMEOUT = 1

# Regular expression for interval/timeout specification
INTERVAL_SPEC = re.compile("^([0-9]+)(s|m|h)?$")
# Conversion factors to seconds
FACTORS = {None: 1, "s": 1, "m": 60, "h": 3600}

def _create_deployment_name(component_name):
    return "dep-{0}".format(component_name)

def _create_service_name(component_name):
    return "{0}".format(component_name)

def _create_exposed_service_name(component_name):
    return ("x{0}".format(component_name))[:63]

def _configure_api():
    # Look for a kubernetes config file in ~/.kube/config
    kubepath = os.path.join(os.environ["HOME"], '.kube/config')
    if os.path.exists(kubepath):
        config.load_kube_config(kubepath)
    else:
        # Maybe we're running in a k8s container and we can use info provided by k8s
        # We would like to use:
        # config.load_incluster_config()
        # but this looks into os.environ for kubernetes host and port, and from
        # the plugin those aren't visible.   So we use the InClusterConfigLoader class,
        # where we can set the environment to what we like.
        # This is probably brittle!  Maybe there's a better alternative.
        localenv = {
            config.incluster_config.SERVICE_HOST_ENV_NAME : "kubernetes.default.svc.cluster.local",
            config.incluster_config.SERVICE_PORT_ENV_NAME : "443"
        }
        config.incluster_config.InClusterConfigLoader(
            token_filename=config.incluster_config.SERVICE_TOKEN_FILENAME,
            cert_filename=config.incluster_config.SERVICE_CERT_FILENAME,
            environ=localenv
        ).load_and_set()

def _parse_interval(t):
    """
    Parse an interval specification
    t can be
       - a simple integer quantity, interpreted as seconds
       - a string representation of a decimal integer, interpreted as seconds
       - a string consisting of a represention of an decimal integer followed by a unit,
         with "s" representing seconds, "m" representing minutes,
         and "h" representing hours
    Used for compatibility with the Docker plugin, where time intervals
    for health checks were specified as strings with a number and a unit.
    See 'intervalspec' above for the regular expression that's accepted.
    """
    m = INTERVAL_SPEC.match(str(t))
    if m:
        time = int(m.group(1)) * FACTORS[m.group(2)]
    else:
        raise ValueError("Bad interval specification: {0}".format(t))
    return time

def _create_probe(hc, port, use_tls=False):
    ''' Create a Kubernetes probe based on info in the health check dictionary hc '''
    probe_type = hc['type']
    probe = None
    period = _parse_interval(hc.get('interval', PROBE_DEFAULT_PERIOD))
    timeout = _parse_interval(hc.get('timeout', PROBE_DEFAULT_TIMEOUT))
    if probe_type in ['http', 'https']:
        probe = client.V1Probe(
          failure_threshold = 1,
          initial_delay_seconds = 5,
          period_seconds = period,
          timeout_seconds = timeout,
          http_get = client.V1HTTPGetAction(
              path = hc['endpoint'],
              port = port,
              scheme = 'HTTPS' if use_tls else probe_type.upper()
          )
        )
    elif probe_type in ['script', 'docker']:
        probe = client.V1Probe(
          failure_threshold = 1,
          initial_delay_seconds = 5,
          period_seconds = period,
          timeout_seconds = timeout,
          _exec = client.V1ExecAction(
              command = [hc['script']]
          )
        )
    return probe

def _create_container_object(name, image, always_pull, use_tls=False, env={}, container_ports=[], volume_mounts = [], readiness = None):
    # Set up environment variables
    # Copy any passed in environment variables
    env_vars = [client.V1EnvVar(name=k, value=env[k]) for k in env.keys()]
    # Add POD_IP with the IP address of the pod running the container
    pod_ip = client.V1EnvVarSource(field_ref = client.V1ObjectFieldSelector(field_path="status.podIP"))
    env_vars.append(client.V1EnvVar(name="POD_IP",value_from=pod_ip))

    # If a health check is specified, create a readiness probe
    # (For an HTTP-based check, we assume it's at the first container port)
    probe = None

    if readiness:
        hc_port = None
        if len(container_ports) > 0:
            hc_port = container_ports[0]
        probe = _create_probe(readiness, hc_port, use_tls)

    # Define container for pod
    return client.V1Container(
        name=name,
        image=image,
        image_pull_policy='Always' if always_pull else 'IfNotPresent',
        env=env_vars,
        ports=[client.V1ContainerPort(container_port=p) for p in container_ports],
        volume_mounts = volume_mounts,
        readiness_probe = probe
    )

def _create_deployment_object(component_name,
                              containers,
                              init_containers,
                              replicas,
                              volumes,
                              labels={},
                              pull_secrets=[]):

    deployment_name = _create_deployment_name(component_name)

    # Label the pod with the deployment name, so we can find it easily
    labels.update({"k8sdeployment" : deployment_name})

    # pull_secrets is a list of the names of the k8s secrets containing docker registry credentials
    # See https://kubernetes.io/docs/concepts/containers/images/#specifying-imagepullsecrets-on-a-pod
    ips = []
    for secret in pull_secrets:
        ips.append(client.V1LocalObjectReference(name=secret))

    # Define pod template
    template = client.V1PodTemplateSpec(
        metadata=client.V1ObjectMeta(labels=labels),
        spec=client.V1PodSpec(hostname=component_name,
                              containers=containers,
                              init_containers=init_containers,
                              volumes=volumes,
                              image_pull_secrets=ips)
    )

    # Define deployment spec
    spec = client.ExtensionsV1beta1DeploymentSpec(
        replicas=replicas,
        template=template
    )

    # Create deployment object
    deployment = client.ExtensionsV1beta1Deployment(
        kind="Deployment",
        metadata=client.V1ObjectMeta(name=deployment_name),
        spec=spec
    )

    return deployment

def _create_service_object(service_name, component_name, service_ports, annotations, labels, service_type):
    service_spec = client.V1ServiceSpec(
        ports=service_ports,
        selector={"app" : component_name},
        type=service_type
    )
    if annotations:
        metadata = client.V1ObjectMeta(name=_create_service_name(service_name), labels=labels, annotations=annotations)
    else:
        metadata = client.V1ObjectMeta(name=_create_service_name(service_name), labels=labels)

    service = client.V1Service(
        kind="Service",
        api_version="v1",
        metadata=metadata,
        spec=service_spec
    )
    return service

def _parse_ports(port_list):
    container_ports = []
    port_map = {}
    for p in port_list:
        try:
            [container, host] = (p.strip()).split(":",2)
            cport = int(container)
            container_ports.append(cport)
            hport = int(host)
            port_map[container] = hport
        except:
            pass    # if something doesn't parse, we just ignore it

    return container_ports, port_map

def _parse_volumes(volume_list):
    volumes = []
    volume_mounts = []
    for v in volume_list:
        vname = str(uuid.uuid4())
        vhost = v['host']['path']
        vcontainer = v['container']['bind']
        vro = (v['container']['mode'] == 'ro')
        volumes.append(client.V1Volume(name=vname, host_path=client.V1HostPathVolumeSource(path=vhost)))
        volume_mounts.append(client.V1VolumeMount(name=vname, mount_path=vcontainer, read_only=vro))

    return volumes, volume_mounts

def _service_exists(namespace, component_name):
    exists = False
    try:
        _configure_api()
        client.CoreV1Api().read_namespaced_service(_create_service_name(component_name), namespace)
        exists = True
    except client.rest.ApiException:
        pass

    return exists

def _patch_deployment(namespace, deployment, modify):
    '''
    Gets the current spec for 'deployment' in 'namespace',
    uses the 'modify' function to change the spec,
    then sends the updated spec to k8s.
    '''
    _configure_api()

    # Get deployment spec
    spec = client.ExtensionsV1beta1Api().read_namespaced_deployment(deployment, namespace)

    # Apply changes to spec
    spec = modify(spec)

    # Patch the deploy with updated spec
    client.ExtensionsV1beta1Api().patch_namespaced_deployment(deployment, namespace, spec)

def _execute_command_in_pod(namespace, pod_name, command):
    '''
    Execute the command (specified by an argv-style list in  the "command" parameter) in
    the specified pod in the specified namespace.  For now at least, we use this only to
    run a notification script in a pod after a configuration change.

    The straightforward way to do this is with the V1 Core API function "connect_get_namespaced_pod_exec".
    Unfortunately due to a bug/limitation in the Python client library, we can't call it directly.
    We have to make the API call through a Websocket connection using the kubernetes.stream wrapper API.
    I'm following the example code at https://github.com/kubernetes-client/python/blob/master/examples/exec.py.
    There are several issues tracking this, in various states.  It isn't clear that there will ever
    be a fix.
        - https://github.com/kubernetes-client/python/issues/58
        - https://github.com/kubernetes-client/python/issues/409
        - https://github.com/kubernetes-client/python/issues/526

    The main consequence of the workaround using "stream" is that the caller does not get an indication
    of the exit code returned by the command when it completes execution.   It turns out that the
    original implementation of notification in the Docker plugin did not use this result, so we can
    still match the original notification functionality.

    The "stream" approach returns a string containing any output sent by the command to stdout or stderr.
    We'll return that so it can logged.
    '''
    _configure_api()
    try:
        output = stream.stream(client.CoreV1Api().connect_get_namespaced_pod_exec,
                             name=pod_name,
                             namespace=namespace,
                             command=command,
                             stdout=True,
                             stderr=True,
                            stdin=False,
                            tty=False)
    except client.rest.ApiException as e:
        # If the exception indicates the pod wasn't found,  it's not a fatal error.
        # It existed when we enumerated the pods for the deployment but no longer exists.
        # Unfortunately, the only way to distinguish a pod not found from any other error
        # is by looking at the reason text.
        # (The ApiException's "status" field should contain the HTTP status code, which would
        # be 404 if the pod isn't found, but empirical testing reveals that "status" is set
        # to zero.)
        if "404 not found" in e.reason.lower():
            output = "Pod not found"
        else:
            raise e

    return {"pod" : pod_name, "output" : output}

def deploy(namespace, component_name, image, replicas, always_pull, k8sconfig, **kwargs):
    '''
    This will create a k8s Deployment and, if needed, one or two k8s Services.
    (We are being opinionated in our use of k8s... this code decides what k8s abstractions and features to use.
    We're not exposing k8s to the component developer and the blueprint author.
    This is a conscious choice.  We want to use k8s in a controlled, consistent way, and we want to hide
    the details from the component developer and the blueprint author.)

    namespace:  the Kubernetes namespace into which the component is deployed
    component_name:  the component name, used to derive names of Kubernetes entities
    image: the docker image for the component being deployed
    replica: the number of instances of the component to be deployed
    always_pull: boolean flag, indicating that Kubernetes should always pull a new copy of
       the Docker image for the component, even if it is already present on the Kubernetes node.
    k8sconfig contains:
        - image_pull_secrets: a list of names of image pull secrets that can be used for retrieving images.
          (DON'T PANIC:  these are just the names of secrets held in the Kubernetes secret store.)
        - filebeat: a dictionary of filebeat sidecar parameters:
            "log_path" : mount point for log volume in filebeat container
            "data_path" : mount point for data volume in filebeat container
            "config_path" : mount point for config volume in filebeat container
            "config_subpath" :  subpath for config data in filebeat container
            "config_map" : ConfigMap holding the filebeat configuration
            "image": Docker image to use for filebeat
        - tls: a dictionary of TLS init container parameters:
            "cert_path": mount point for certificate volume in init container
            "image": Docker image to use for TLS init container
    kwargs may have:
        - volumes:  array of volume objects, where a volume object is:
            {"host":{"path": "/path/on/host"}, "container":{"bind":"/path/on/container","mode":"rw_or_ro"}
        - ports: array of strings in the form "container_port:host_port"
        - env: map of name-value pairs ( {name0: value0, name1: value1...}
        - msb_list: array of msb objects, where an msb object is as described in msb/msb.py.
        - log_info: an object with info for setting up ELK logging, with the form:
            {"log_directory": "/path/to/container/log/directory", "alternate_fb_path" : "/alternate/sidecar/log/path"}
        - tls_info: an object with info for setting up TLS (HTTPS), with the form:
            {"use_tls": true, "cert_directory": "/path/to/container/cert/directory" }
        - labels: dict with label-name/label-value pairs, e.g. {"cfydeployment" : "lsdfkladflksdfsjkl", "cfynode":"mycomponent"}
            These label will be set on all the pods deployed as a result of this deploy() invocation.
        - readiness: dict with health check info; if present, used to create a readiness probe for the main container.  Includes:
            - type: check is done by making http(s) request to an endpoint ("http", "https") or by exec'ing a script in the container ("script", "docker")
            - interval: period (in seconds) between probes
            - timeout:  time (in seconds) to allow a probe to complete
            - endpoint: the path portion of the URL that points to the readiness endpoint for "http" and "https" types
            - path: the full path to the script to be executed in the container for "script" and "docker" types

    '''

    deployment_ok = False
    cip_service_created = False
    deployment_description = {
        "namespace": namespace,
        "deployment": '',
        "services": []
    }

    try:
        _configure_api()

        # Get API handles
        core = client.CoreV1Api()
        ext = client.ExtensionsV1beta1Api()

        # Parse the port mapping into [container_port,...] and [{"host_port" : "container_port"},...]
        container_ports, port_map = _parse_ports(kwargs.get("ports", []))

        # Parse the volumes list into volumes and volume_mounts for the deployment
        volumes, volume_mounts = _parse_volumes(kwargs.get("volumes",[]))

        # Initialize the list of containers that will be part of the pod
        containers = []
        init_containers = []

        # Set up the ELK logging sidecar container, if needed
        log_info = kwargs.get("log_info")
        if log_info and "log_directory" in log_info:
            log_dir = log_info["log_directory"]
            fb = k8sconfig["filebeat"]
            sidecar_volume_mounts = []

            # Create the volume for component log files and volume mounts for the component and sidecar containers
            volumes.append(client.V1Volume(name="component-log", empty_dir=client.V1EmptyDirVolumeSource()))
            volume_mounts.append(client.V1VolumeMount(name="component-log", mount_path=log_dir))
            sc_path = log_info["alternate_fb_path"] if "alternate_fb_path" in log_info  \
                else "{0}/{1}".format(fb["log_path"], component_name)
            sidecar_volume_mounts.append(client.V1VolumeMount(name="component-log", mount_path=sc_path))

            # Create the volume for sidecar data and the volume mount for it
            volumes.append(client.V1Volume(name="filebeat-data", empty_dir=client.V1EmptyDirVolumeSource()))
            sidecar_volume_mounts.append(client.V1VolumeMount(name="filebeat-data", mount_path=fb["data_path"]))

            # Create the container for the sidecar
            containers.append(_create_container_object("filebeat", fb["image"], False, False, {}, [], sidecar_volume_mounts))

            # Create the volume for the sidecar configuration data and the volume mount for it
            # The configuration data is in a k8s ConfigMap that should be created when DCAE is installed.
            volumes.append(
                client.V1Volume(name="filebeat-conf", config_map=client.V1ConfigMapVolumeSource(name=fb["config_map"])))
            sidecar_volume_mounts.append(
                client.V1VolumeMount(name="filebeat-conf", mount_path=fb["config_path"], sub_path=fb["config_subpath"]))

        # Set up the TLS init container, if needed
        tls_info = kwargs.get("tls_info")
        use_tls = False
        if tls_info and "use_tls" in tls_info and tls_info["use_tls"]:
            if "cert_directory" in tls_info and len(tls_info["cert_directory"]) > 0:
                use_tls = True
                tls_config = k8sconfig["tls"]

                # Create the certificate volume and volume mounts
                volumes.append(client.V1Volume(name="tls-info", empty_dir=client.V1EmptyDirVolumeSource()))
                volume_mounts.append(client.V1VolumeMount(name="tls-info", mount_path=tls_info["cert_directory"]))
                init_volume_mounts = [client.V1VolumeMount(name="tls-info", mount_path=tls_config["cert_path"])]

                # Create the init container
                init_containers.append(_create_container_object("init-tls", tls_config["image"], False, False, {}, [], init_volume_mounts))

        # Create the container for the component
        # Make it the first container in the pod
        containers.insert(0, _create_container_object(component_name, image, always_pull, use_tls, kwargs.get("env", {}), container_ports, volume_mounts, kwargs["readiness"]))

        # Build the k8s Deployment object
        labels = kwargs.get("labels", {})
        labels.update({"app": component_name})
        dep = _create_deployment_object(component_name, containers, init_containers, replicas, volumes, labels, pull_secrets=k8sconfig["image_pull_secrets"])

        # Have k8s deploy it
        ext.create_namespaced_deployment(namespace, dep)
        deployment_ok = True
        deployment_description["deployment"] = _create_deployment_name(component_name)

        # Create service(s), if a port mapping is specified
        if port_map:
            service_ports = []      # Ports exposed internally on the k8s network
            exposed_ports = []      # Ports to be mapped to ports on the k8s nodes via NodePort
            for cport, hport in port_map.iteritems():
                service_ports.append(client.V1ServicePort(port=int(cport),name="port-{}".format(cport)))
                if int(hport) != 0:
                    exposed_ports.append(client.V1ServicePort(port=int(cport), node_port=int(hport),name="xport-{}".format(cport)))

            # If there are ports to be exposed via MSB, set up the annotation for the service
            msb_list = kwargs.get("msb_list")
            annotations = msb.create_msb_annotation(msb_list) if msb_list else ''

            # Create a ClusterIP service for access via the k8s network
            service = _create_service_object(_create_service_name(component_name), component_name, service_ports, annotations, labels, "ClusterIP")
            core.create_namespaced_service(namespace, service)
            cip_service_created = True
            deployment_description["services"].append(_create_service_name(component_name))

            # If there are ports to be exposed on the k8s nodes, create a "NodePort" service
            if len(exposed_ports) > 0:
                exposed_service = \
                    _create_service_object(_create_exposed_service_name(component_name), component_name, exposed_ports, '', labels, "NodePort")
                core.create_namespaced_service(namespace, exposed_service)
                deployment_description["services"].append(_create_exposed_service_name(component_name))

    except Exception as e:
        # If the ClusterIP service was created, delete the service:
        if cip_service_created:
            core.delete_namespaced_service(_create_service_name(component_name), namespace)
        # If the deployment was created but not the service, delete the deployment
        if deployment_ok:
            client.ExtensionsV1beta1Api().delete_namespaced_deployment(_create_deployment_name(component_name), namespace, client.V1DeleteOptions())
        raise e

    return dep, deployment_description

def undeploy(deployment_description):
    _configure_api()

    namespace = deployment_description["namespace"]

    # remove any services associated with the component
    for service in deployment_description["services"]:
        client.CoreV1Api().delete_namespaced_service(service, namespace)

    # Have k8s delete the underlying pods and replicaset when deleting the deployment.
    options = client.V1DeleteOptions(propagation_policy="Foreground")
    client.ExtensionsV1beta1Api().delete_namespaced_deployment(deployment_description["deployment"], namespace, options)

def is_available(namespace, component_name):
    _configure_api()
    dep_status = client.AppsV1beta1Api().read_namespaced_deployment_status(_create_deployment_name(component_name), namespace)
    # Check if the number of available replicas is equal to the number requested and that the replicas match the current spec
    # This check can be used to verify completion of an initial deployment, a scale operation, or an update operation
    return dep_status.status.available_replicas == dep_status.spec.replicas and dep_status.status.updated_replicas == dep_status.spec.replicas

def scale(deployment_description, replicas):
    ''' Trigger a scaling operation by updating the replica count for the Deployment '''

    def update_replica_count(spec):
        spec.spec.replicas = replicas
        return spec

    _patch_deployment(deployment_description["namespace"], deployment_description["deployment"], update_replica_count)

def upgrade(deployment_description, image, container_index = 0):
    ''' Trigger a rolling upgrade by sending a new image name/tag to k8s '''

    def update_image(spec):
        spec.spec.template.spec.containers[container_index].image = image
        return spec

    _patch_deployment(deployment_description["namespace"], deployment_description["deployment"], update_image)

def rollback(deployment_description, rollback_to=0):
    '''
    Undo upgrade by rolling back to a previous revision of the deployment.
    By default, go back one revision.
    rollback_to can be used to supply a specific revision number.
    Returns the image for the app container and the replica count from the rolled-back deployment
    '''
    '''
    2018-07-13
    Currently this does not work due to a bug in the create_namespaced_deployment_rollback() method.
    The k8s python client code throws an exception while processing the response from the API.
    See:
       - https://github.com/kubernetes-client/python/issues/491
       - https://github.com/kubernetes/kubernetes/pull/63837
    The fix has been merged into the master branch but is not in the latest release.
    '''
    _configure_api()
    deployment = deployment_description["deployment"]
    namespace = deployment_description["namespace"]

    # Initiate the rollback
    client.ExtensionsV1beta1Api().create_namespaced_deployment_rollback(
        deployment,
        namespace,
        client.AppsV1beta1DeploymentRollback(name=deployment, rollback_to=client.AppsV1beta1RollbackConfig(revision=rollback_to)))

    # Read back the spec for the rolled-back deployment
    spec = client.ExtensionsV1beta1Api().read_namespaced_deployment(deployment, namespace)
    return spec.spec.template.spec.containers[0].image, spec.spec.replicas

def execute_command_in_deployment(deployment_description, command):
    '''
    Enumerates the pods in the k8s deployment identified by "deployment_description",
    then executes the command (represented as an argv-style list) in "command" in
    container 0 (the main application container) each of those pods.

    Note that the sets of pods associated with a deployment can change over time.  The
    enumeration is a snapshot at one point in time.  The command will not be executed in
    pods that are created after the initial enumeration.   If a pod disappears after the
    initial enumeration and before the command is executed, the attempt to execute the
    command will fail.  This is not treated as a fatal error.

    This approach is reasonable for the one current use case for "execute_command":  running a
    script to notify a container that its configuration has changed as a result of a
    policy change.  In this use case, the new configuration information is stored into
    the configuration store (Consul), the pods are enumerated, and the command is executed.
    If a pod disappears after the enumeration, the fact that the command cannot be run
    doesn't matter--a nonexistent pod doesn't need to be reconfigured.  Similarly, a pod that
    comes up after the enumeration will get its initial configuration from the updated version
    in Consul.

    The optimal solution here would be for k8s to provide an API call to execute a command in
    all of the pods for a deployment.   Unfortunately, k8s does not provide such a call--the
    only call provided by k8s operates at the pod level, not the deployment level.

    Another interesting k8s factoid: there's no direct way to list the pods belong to a
    particular k8s deployment.   The deployment code above sets a label ("k8sdeployment") on
    the pod that has the k8s deployment name.  To list the pods, the code below queries for
    pods with the label carrying the deployment name.
    '''

    _configure_api()
    deployment = deployment_description["deployment"]
    namespace = deployment_description["namespace"]

    # Get names of all the running pods belonging to the deployment
    pod_names = [pod.metadata.name for pod in client.CoreV1Api().list_namespaced_pod(
        namespace = namespace,
        label_selector = "k8sdeployment={0}".format(deployment),
        field_selector = "status.phase=Running"
    ).items]

    def do_execute(pod_name):
        return _execute_command_in_pod(namespace, pod_name, command)

    # Execute command in the running pods
    return map(do_execute, pod_names)