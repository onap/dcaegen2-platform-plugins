# ============LICENSE_START=======================================================
# org.onap.dcae
# ================================================================================
# Copyright (c) 2019-2020 AT&T Intellectual Property. All rights reserved.
# Copyright (c) 2020 Pantheon.tech. All rights reserved.
# Copyright (c) 2020-2021 Nokia. All rights reserved.
# Copyright (c) 2020 J. F. Lucas.  All rights reserved.
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
from distutils import util
import os
import re
import uuid
import base64

from binascii import hexlify
from kubernetes import config, client, stream
from .sans_parser import SansParser

# Default values for readiness probe
PROBE_DEFAULT_PERIOD = 15
PROBE_DEFAULT_TIMEOUT = 1

# Location of k8s cluster config file ("kubeconfig")
K8S_CONFIG_PATH = "/opt/onap/kube/kubeconfig"

# Regular expression for interval/timeout specification
INTERVAL_SPEC = re.compile("^([0-9]+)(s|m|h)?$")
# Conversion factors to seconds
FACTORS = {None: 1, "s": 1, "m": 60, "h": 3600}

# Regular expression for port mapping
# group 1: container port
# group 2: / + protocol
# group 3: protocol
# group 4: host port
PORTS = re.compile("^([0-9]+)(/(udp|UDP|tcp|TCP))?:([0-9]+)$")

# Constants for external_cert
MOUNT_PATH = "/etc/onap/oom/certservice/certs/"
DEFAULT_CERT_TYPE = "p12"


def _create_deployment_name(component_name):
    return "dep-{0}".format(component_name)[:63]


def _create_service_name(component_name):
    return "{0}".format(component_name)[:63]


def _create_exposed_service_name(component_name):
    return ("x{0}".format(component_name))[:63]


def _create_exposed_v6_service_name(component_name):
    return ("x{0}-ipv6".format(component_name))[:63]


def _configure_api(location=None):
    # Look for a kubernetes config file
    if os.path.exists(K8S_CONFIG_PATH):
        config.load_kube_config(config_file=K8S_CONFIG_PATH, context=location, persist_config=False)
    else:
        # Maybe we're running in a k8s container and we can use info provided by k8s
        # We would like to use:
        # config.load_incluster_config()
        # but this looks into os.environ for kubernetes host and port, and from
        # the plugin those aren't visible.   So we use the InClusterConfigLoader class,
        # where we can set the environment to what we like.
        # This is probably brittle!  Maybe there's a better alternative.
        localenv = {
            config.incluster_config.SERVICE_HOST_ENV_NAME: "kubernetes.default.svc.cluster.local",
            config.incluster_config.SERVICE_PORT_ENV_NAME: "443"
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


def _create_probe(hc, port):
    """ Create a Kubernetes probe based on info in the health check dictionary hc """
    probe_type = hc['type']
    probe = None
    period = _parse_interval(hc.get('interval', PROBE_DEFAULT_PERIOD))
    timeout = _parse_interval(hc.get('timeout', PROBE_DEFAULT_TIMEOUT))
    if probe_type in ['http', 'https']:
        probe = client.V1Probe(
            failure_threshold=1,
            initial_delay_seconds=5,
            period_seconds=period,
            timeout_seconds=timeout,
            http_get=client.V1HTTPGetAction(
                path=hc['endpoint'],
                port=port,
                scheme=probe_type.upper()
            )
        )
    elif probe_type in ['script', 'docker']:
        probe = client.V1Probe(
            failure_threshold=1,
            initial_delay_seconds=5,
            period_seconds=period,
            timeout_seconds=timeout,
            _exec=client.V1ExecAction(
                command=hc['script'].split()
            )
        )
    return probe


def _create_resources(resources=None):
    if resources is not None:
        resources_obj = client.V1ResourceRequirements(
            limits=resources.get("limits"),
            requests=resources.get("requests")
        )
        return resources_obj
    else:
        return None


def _create_container_object(name, image, always_pull, **kwargs):
    # Set up environment variables
    # Copy any passed in environment variables
    env = kwargs.get('env') or {}
    env_vars = [client.V1EnvVar(name=k, value=env[k]) for k in env]

    # Add POD_IP with the IP address of the pod running the container
    pod_ip = client.V1EnvVarSource(field_ref=client.V1ObjectFieldSelector(field_path="status.podIP"))
    env_vars.append(client.V1EnvVar(name="POD_IP", value_from=pod_ip))

    # Add envs from Secret
    if 'env_from_secret' in kwargs:
        for env in kwargs.get('env_from_secret').values():
            secret_key_selector = client.V1SecretKeySelector(key=env["secret_key"], name=env["secret_name"])
            env_var_source = client.V1EnvVarSource(secret_key_ref=secret_key_selector)
            env_vars.append(client.V1EnvVar(name=env["env_name"], value_from=env_var_source))

    # If a health check is specified, create a readiness/liveness probe
    # (For an HTTP-based check, we assume it's at the first container port)
    readiness = kwargs.get('readiness')
    liveness = kwargs.get('liveness')
    resources = kwargs.get('resources')
    container_ports = kwargs.get('container_ports') or []

    hc_port = container_ports[0][0] if container_ports else None
    probe = _create_probe(readiness, hc_port) if readiness else None
    live_probe = _create_probe(liveness, hc_port) if liveness else None
    resources_obj = _create_resources(resources) if resources else None
    port_objs = [client.V1ContainerPort(container_port=port, protocol=proto)
                 for port, proto in container_ports]

    # Define container for pod
    return client.V1Container(
        name=name,
        image=image,
        image_pull_policy='Always' if always_pull else 'IfNotPresent',
        env=env_vars,
        ports=port_objs,
        volume_mounts=kwargs.get('volume_mounts') or [],
        resources=resources_obj,
        readiness_probe=probe,
        liveness_probe=live_probe
    )


def _create_deployment_object(component_name,
                              containers,
                              init_containers,
                              replicas,
                              volumes,
                              labels=None,
                              pull_secrets=None):
    if labels is None:
        labels = {}
    if pull_secrets is None:
        pull_secrets = []
    deployment_name = _create_deployment_name(component_name)

    # Label the pod with the deployment name, so we can find it easily
    labels.update({"k8sdeployment": deployment_name})

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
    spec = client.V1DeploymentSpec(
        replicas=replicas,
        selector=client.V1LabelSelector(match_labels=labels),
        template=template
    )

    # Create deployment object
    deployment = client.V1Deployment(
        api_version="apps/v1",
        kind="Deployment",
        metadata=client.V1ObjectMeta(name=deployment_name, labels=labels),
        spec=spec
    )

    return deployment


def _create_service_object(service_name, component_name, service_ports, annotations, labels, service_type, ip_family):
    service_spec = client.V1ServiceSpec(
        ports=service_ports,
        selector={"app": component_name},
        type=service_type,
        ip_family=ip_family
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


def create_secret_with_password(namespace, secret_prefix, password_key, password_length):
    """
    Creates K8s secret object with a generated password.
    Returns: secret name and data key.

    Example usage:
         create_secret_with_password('onap', 'dcae-keystore-password-', 128)
    """
    password = _generate_password(password_length)
    password_base64 = _encode_base64(password)

    metadata = {'generateName': secret_prefix, 'namespace': namespace}
    key = password_key
    data = {key: password_base64}

    response = _create_k8s_secret(namespace, metadata, data, 'Opaque')
    secret_name = response.metadata.name
    return secret_name, key


def _generate_password(length):
    rand = os.urandom(length)
    password = hexlify(rand)
    return password.decode("ascii");


def _encode_base64(value):
    value_bytes = value.encode("ascii")
    base64_encoded_bytes = base64.b64encode(value_bytes)
    encoded_value = base64_encoded_bytes.decode("ascii")
    return encoded_value


def _create_k8s_secret(namespace, metadata, data, secret_type):
    api_version = 'v1'
    kind = 'Secret'
    body = client.V1Secret(api_version, data, kind, metadata, type=secret_type)

    response = client.CoreV1Api().create_namespaced_secret(namespace, body)
    return response


def parse_ports(port_list):
    """
    Parse the port list into a list of container ports (needed to create the container)
    and to a set of port mappings to set up k8s services.
    """
    container_ports = []
    port_map = {}
    for p in port_list:
        ipv6 = False
        if type(p) is dict:
            ipv6 = "ipv6" in p and p['ipv6']
            p = "".join(str(v) for v in p['concat'])
        m = PORTS.match(p.strip())
        if m:
            cport = int(m.group(1))
            hport = int(m.group(4))
            if m.group(3):
                proto = (m.group(3)).upper()
            else:
                proto = "TCP"
            port = (cport, proto)
            if port not in container_ports:
                container_ports.append(port)
            port_map[(cport, proto, ipv6)] = hport
        else:
            raise ValueError("Bad port specification: {0}".format(p))

    return container_ports, port_map


def _parse_volumes(volume_list):
    volumes = []
    volume_mounts = []
    for v in volume_list:
        vname = str(uuid.uuid4())
        vcontainer = v['container']['bind']
        vro = (v['container'].get('mode') == 'ro')
        if ('host' in v) and ('path' in v['host']):
            vhost = v['host']['path']
            volumes.append(client.V1Volume(name=vname, host_path=client.V1HostPathVolumeSource(path=vhost)))
        if ('config_volume' in v) and ('name' in v['config_volume']):
            vconfig_volume = v['config_volume']['name']
            volumes.append(client.V1Volume(name=vname, config_map=client.V1ConfigMapVolumeSource(default_mode=0o0644,
                                                                                                 name=vconfig_volume,
                                                                                                 optional=True)))
        volume_mounts.append(client.V1VolumeMount(name=vname, mount_path=vcontainer, read_only=vro))

    return volumes, volume_mounts


def _add_elk_logging_sidecar(containers, volumes, volume_mounts, component_name, log_info, filebeat):
    if not log_info or not filebeat:
        return
    log_dir = log_info.get("log_directory")
    if not log_dir:
        return
    sidecar_volume_mounts = []

    # Create the volume for component log files and volume mounts for the component and sidecar containers
    volumes.append(client.V1Volume(name="component-log", empty_dir=client.V1EmptyDirVolumeSource()))
    volume_mounts.append(client.V1VolumeMount(name="component-log", mount_path=log_dir))
    sc_path = log_info.get("alternate_fb_path") or "{0}/{1}".format(filebeat["log_path"], component_name)
    sidecar_volume_mounts.append(client.V1VolumeMount(name="component-log", mount_path=sc_path))

    # Create the volume for sidecar data and the volume mount for it
    volumes.append(client.V1Volume(name="filebeat-data", empty_dir=client.V1EmptyDirVolumeSource()))
    sidecar_volume_mounts.append(client.V1VolumeMount(name="filebeat-data", mount_path=filebeat["data_path"]))

    # Create the volume for the sidecar configuration data and the volume mount for it
    # The configuration data is in a k8s ConfigMap that should be created when DCAE is installed.
    volumes.append(
        client.V1Volume(name="filebeat-conf", config_map=client.V1ConfigMapVolumeSource(name=filebeat["config_map"])))
    sidecar_volume_mounts.append(
        client.V1VolumeMount(name="filebeat-conf", mount_path=filebeat["config_path"],
                             sub_path=filebeat["config_subpath"]))

    # Finally create the container for the sidecar
    containers.append(
        _create_container_object("filebeat", filebeat["image"], False, volume_mounts=sidecar_volume_mounts))


def _add_tls_init_container(ctx, init_containers, volumes, volume_mounts, tls_info, tls_config):
    # Adds an InitContainer to the pod to set up TLS certificate information.  For components that act as a server(
    # tls_info["use_tls"] is True), the InitContainer will populate a directory with server and CA certificate
    # materials in various formats.   For other components (tls_info["use_tls"] is False, or tls_info is not
    # specified), the InitContainer will populate a directory with CA certificate materials in PEM and JKS formats.
    # In either case, the certificate directory is mounted onto the component container filesystem at the location
    # specified by tls_info["component_cert_dir"], if present, otherwise at the configured default mount point (
    # tls_config["component_cert_dir"]).
    docker_image = tls_config["image"]
    ctx.logger.info("Creating init container: TLS \n  * [" + docker_image + "]")

    cert_directory = tls_info.get("cert_directory") or tls_config.get("component_cert_dir")
    env = {}
    env["TLS_SERVER"] = "true" if tls_info.get("use_tls") else "false"

    # Create the certificate volume and volume mounts
    volumes.append(client.V1Volume(name="tls-info", empty_dir=client.V1EmptyDirVolumeSource()))
    volume_mounts.append(client.V1VolumeMount(name="tls-info", mount_path=cert_directory))
    init_volume_mounts = [client.V1VolumeMount(name="tls-info", mount_path=tls_config["cert_path"])]

    # Create the init container
    init_containers.append(
        _create_container_object("init-tls", docker_image, False, volume_mounts=init_volume_mounts, env=env))


def _add_external_tls_init_container(ctx, init_containers, volumes, external_cert, external_tls_config):
    # Adds an InitContainer to the pod which will generate external TLS certificates.
    docker_image = external_tls_config["image_tag"]
    ctx.logger.info("Creating init container: external TLS \n  * [" + docker_image + "]")

    env = {}
    env_from_secret = {}
    output_path = external_cert.get("external_cert_directory")
    if not output_path.endswith('/'):
        output_path += '/'

    keystore_secret_key = external_tls_config.get("keystore_secret_key")
    truststore_secret_key = external_tls_config.get("truststore_secret_key")

    env["REQUEST_URL"] = external_tls_config.get("request_url")
    env["REQUEST_TIMEOUT"] = external_tls_config.get("timeout")
    env["OUTPUT_PATH"] = output_path + "external"
    env["OUTPUT_TYPE"] = external_cert.get("cert_type")
    env["CA_NAME"] = external_cert.get("ca_name")
    env["COMMON_NAME"] = external_cert.get("external_certificate_parameters").get("common_name")
    env["ORGANIZATION"] = external_tls_config.get("organization")
    env["ORGANIZATION_UNIT"] = external_tls_config.get("organizational_unit")
    env["LOCATION"] = external_tls_config.get("location")
    env["STATE"] = external_tls_config.get("state")
    env["COUNTRY"] = external_tls_config.get("country")
    env["SANS"] = external_cert.get("external_certificate_parameters").get("sans")
    env["KEYSTORE_PATH"] = MOUNT_PATH + keystore_secret_key
    env["TRUSTSTORE_PATH"] = MOUNT_PATH + truststore_secret_key
    env_from_secret["KEYSTORE_PASSWORD"] = \
        {"env_name": "KEYSTORE_PASSWORD",
         "secret_name": external_tls_config.get("keystore_password_secret_name"),
         "secret_key": external_tls_config.get("keystore_password_secret_key")}
    env_from_secret["TRUSTSTORE_PASSWORD"] = \
        {"env_name": "TRUSTSTORE_PASSWORD",
         "secret_name": external_tls_config.get("truststore_password_secret_name"),
         "secret_key": external_tls_config.get("truststore_password_secret_key")}
    # Create the volumes and volume mounts
    projected_volume = _create_projected_tls_volume(external_tls_config.get("cert_secret_name"),
                                                    keystore_secret_key,
                                                    truststore_secret_key)

    volumes.append(client.V1Volume(name="tls-volume", projected=projected_volume))
    init_volume_mounts = [
        client.V1VolumeMount(name="tls-info", mount_path=external_cert.get("external_cert_directory")),
        client.V1VolumeMount(name="tls-volume", mount_path=MOUNT_PATH)]

    # Create the init container
    init_containers.append(
        _create_container_object("cert-service-client", docker_image, False, volume_mounts=init_volume_mounts, env=env, env_from_secret=env_from_secret))


def _create_projected_tls_volume(secret_name, keystore_secret_key, truststore_secret_key):
    items = [
        client.V1KeyToPath(key=keystore_secret_key, path=keystore_secret_key),
        client.V1KeyToPath(key=truststore_secret_key, path=truststore_secret_key)]
    secret_projection = client.V1SecretProjection(name=secret_name, items=items)
    volume_projection = [client.V1VolumeProjection(secret=secret_projection)]
    projected_volume = client.V1ProjectedVolumeSource(sources=volume_projection)
    return projected_volume


def _add_cert_post_processor_init_container(ctx, init_containers, tls_info, tls_config, external_cert,
                                            cert_post_processor_config, isCertManagerIntegration):
    # Adds an InitContainer to the pod to merge TLS and external TLS truststore into single file.
    docker_image = cert_post_processor_config["image_tag"]
    ctx.logger.info("Creating init container: cert post processor \n  * [" + docker_image + "]")

    tls_cert_dir = tls_info.get("cert_directory") or tls_config.get("component_cert_dir")
    if not tls_cert_dir.endswith('/'):
        tls_cert_dir += '/'

    tls_cert_file_path = tls_cert_dir + "trust.jks"
    tls_cert_file_pass = tls_cert_dir + "trust.pass"

    ext_cert_dir = tls_cert_dir + "external/"

    output_type = (external_cert.get("cert_type") or DEFAULT_CERT_TYPE).lower()
    ext_truststore_path = ext_cert_dir + "truststore." + _get_file_extension(output_type)
    ext_truststore_pass = ''
    if output_type != 'pem':
        ext_truststore_pass = ext_cert_dir + "truststore.pass"

    env = {"TRUSTSTORES_PATHS": tls_cert_file_path + ":" + ext_truststore_path,
           "TRUSTSTORES_PASSWORDS_PATHS": tls_cert_file_pass + ":" + ext_truststore_pass,
           "KEYSTORE_SOURCE_PATHS": _get_keystore_source_paths(output_type, ext_cert_dir),
           "KEYSTORE_DESTINATION_PATHS": _get_keystore_destination_paths(output_type, tls_cert_dir)}

    ctx.logger.info("TRUSTSTORES_PATHS:            " + env["TRUSTSTORES_PATHS"])
    ctx.logger.info("TRUSTSTORES_PASSWORDS_PATHS:  " + env["TRUSTSTORES_PASSWORDS_PATHS"])
    ctx.logger.info("KEYSTORE_SOURCE_PATHS:        " + env["KEYSTORE_SOURCE_PATHS"])
    ctx.logger.info("KEYSTORE_DESTINATION_PATHS:   " + env["KEYSTORE_DESTINATION_PATHS"])

    # Create the volumes and volume mounts
    init_volume_mounts = [client.V1VolumeMount(name="tls-info", mount_path=tls_cert_dir)]
    if isCertManagerIntegration:
        init_volume_mounts.append(client.V1VolumeMount(
            name="certmanager-certs-volume", mount_path=ext_cert_dir))
    # Create the init container
    init_containers.append(
        _create_container_object("cert-post-processor", docker_image, False, volume_mounts=init_volume_mounts, env=env))


def _get_file_extension(output_type):
    return {
        'p12': 'p12',
        'pem': 'pem',
        'jks': 'jks',
    }[output_type]


def _get_keystore_source_paths(output_type, ext_cert_dir):
    source_paths_template = {
        'p12': "{0}keystore.p12:{0}keystore.pass",
        'jks': "{0}keystore.jks:{0}keystore.pass",
        'pem': "{0}keystore.pem:{0}key.pem",
    }[output_type]
    return source_paths_template.format(ext_cert_dir)


def _get_keystore_destination_paths(output_type, tls_cert_dir):
    destination_paths_template = {
        'p12': "{0}cert.p12:{0}p12.pass",
        'jks': "{0}cert.jks:{0}jks.pass",
        'pem': "{0}cert.pem:{0}key.pem",
    }[output_type]
    return destination_paths_template.format(tls_cert_dir)


def _process_port_map(port_map):
    service_ports = []  # Ports exposed internally on the k8s network
    exposed_ports = []  # Ports to be mapped to ports on the k8s nodes via NodePort
    exposed_ports_ipv6 = []
    for (cport, proto, ipv6), hport in port_map.items():
        name = "xport-{0}-{1}".format(proto[0].lower(), cport)
        cport = int(cport)
        hport = int(hport)
        port = client.V1ServicePort(port=cport, protocol=proto, name=name[1:])
        if port not in service_ports:
            service_ports.append(port)
        if hport != 0:
            if ipv6:
                exposed_ports_ipv6.append(client.V1ServicePort(port=cport, protocol=proto, node_port=hport, name=name))
            else:
                exposed_ports.append(client.V1ServicePort(port=cport, protocol=proto, node_port=hport, name=name))
    return service_ports, exposed_ports, exposed_ports_ipv6


def _service_exists(location, namespace, component_name):
    exists = False
    try:
        _configure_api(location)
        client.CoreV1Api().read_namespaced_service(_create_service_name(component_name), namespace)
        exists = True
    except client.rest.ApiException:
        pass

    return exists


def _patch_deployment(location, namespace, deployment, modify):
    '''
    Gets the current spec for 'deployment' in 'namespace'
    in the k8s cluster at 'location',
    uses the 'modify' function to change the spec,
    then sends the updated spec to k8s.
    '''
    _configure_api(location)

    # Get deployment spec
    spec = client.AppsV1Api().read_namespaced_deployment(deployment, namespace)

    # Apply changes to spec
    spec = modify(spec)

    # Patch the deploy with updated spec
    client.AppsV1Api().patch_namespaced_deployment(deployment, namespace, spec)


def _execute_command_in_pod(location, namespace, pod_name, command):
    '''
    Execute the command (specified by an argv-style list in  the "command" parameter) in
    the specified pod in the specified namespace at the specified location.
    For now at least, we use this only to
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
    _configure_api(location)
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

    return {"pod": pod_name, "output": output}


def _create_certificate_subject(external_tls_config):
    """
    Map parameters to custom resource subject
    """
    organization = external_tls_config.get("organization")
    organization_unit = external_tls_config.get("organizational_unit")
    country = external_tls_config.get("country")
    location = external_tls_config.get("location")
    state = external_tls_config.get("state")
    subject = {
        "organizations": [organization],
        "countries": [country],
        "localities": [location],
        "provinces": [state],
        "organizationalUnits": [organization_unit]
    }
    return subject


def _create_keystores_object(type, password_secret):
    """
    Create keystore property (JKS and PKC12 certificate) for custom resource
    """
    return {type: {
        "create": True,
        "passwordSecretRef": {
            "name": password_secret,
            "key": "password"
        }}}


def _get_keystores_object_type(output_type):
    """
    Map config type to custom resource cert type
    """
    return {
        'p12': 'pkcs12',
        'jks': 'jks',
    }[output_type]


def _create_projected_volume_with_password(cert_type, cert_secret_name, password_secret_name, password_secret_key):
    """
    Create volume for password protected certificates.
    Secret contains passwords must be provided
    """
    extension = _get_file_extension(cert_type)
    keystore_file_name = "keystore." + extension
    truststore_file_name = "truststore." + extension
    items = [client.V1KeyToPath(key=keystore_file_name, path=keystore_file_name),
             client.V1KeyToPath(key=truststore_file_name, path=truststore_file_name)]
    passwords = [client.V1KeyToPath(key=password_secret_key, path="keystore.pass"), client.V1KeyToPath(key=password_secret_key, path="truststore.pass")]

    sec_projection = client.V1SecretProjection(name=cert_secret_name, items=items)
    sec_passwords_projection = client.V1SecretProjection(name=password_secret_name, items=passwords)
    sec_volume_projection = client.V1VolumeProjection(secret=sec_projection)
    sec_passwords_volume_projection = client.V1VolumeProjection(secret=sec_passwords_projection)

    return [sec_volume_projection, sec_passwords_volume_projection]


def _create_pem_projected_volume(cert_secret_name):
    """
    Create volume for pem certificate
    """
    items = [client.V1KeyToPath(key="tls.crt", path="keystore.pem"),
             client.V1KeyToPath(key="ca.crt", path="truststore.pem"),
             client.V1KeyToPath(key="tls.key", path="key.pem")]
    sec_projection = client.V1SecretProjection(name=cert_secret_name, items=items)
    return [client.V1VolumeProjection(secret=sec_projection)]


def create_certificate_object(ctx, cert_secret_name, external_cert_data, external_tls_config, cert_name, issuer):
    """
    Create cert-manager certificate custom resource object
    """
    common_name = external_cert_data.get("external_certificate_parameters").get("common_name")
    subject = _create_certificate_subject(external_tls_config)

    custom_resource = {
        "apiVersion": "cert-manager.io/v1",
        "kind": "Certificate",
        "metadata": {"name": cert_name },
        "spec": {
            "secretName": cert_secret_name,
            "commonName": common_name,
            "issuerRef": {
                "group": "certmanager.onap.org",
                "kind": "CMPv2Issuer",
                "name": issuer
            }
        }
    }
    custom_resource.get("spec")["subject"] = subject

    raw_sans = external_cert_data.get("external_certificate_parameters").get("sans")
    ctx.logger.info("Read SANS property: " + str(raw_sans))
    sans = SansParser().parse_sans(raw_sans)
    ctx.logger.info("Parsed SANS: " + str(sans))

    if len(sans["ips"]) > 0:
        custom_resource.get("spec")["ipAddresses"] = sans["ips"]
    if len(sans["dnss"]) > 0:
        custom_resource.get("spec")["dnsNames"] = sans["dnss"]
    if len(sans["emails"]) > 0:
        custom_resource.get("spec")["emailAddresses"] = sans["emails"]
    if len(sans["uris"]) > 0:
        custom_resource.get("spec")["uris"] = sans["uris"]

    return custom_resource


def _create_certificate_custom_resource(ctx, external_cert_data, external_tls_config, issuer, namespace, component_name, volumes, volume_mounts, deployment_description):
    """
    Create certificate custom resource for provided configuration
    :param ctx: context
    :param external_cert_data: object contains certificate common name and
    SANs list
    :param external_tls_config: object contains information about certificate subject
    :param issuer: issuer-name
    :param namespace: namespace
    :param component_name: component name
    :param volumes: list of deployment volume
    :param volume_mounts: list of deployment volume mounts
    :param deployment_description: list contains deployment information,
    method appends created cert and secrets
    """
    ctx.logger.info("Creating certificate custom resource")
    ctx.logger.info("External cert data: " + str(external_cert_data))

    cert_type = (external_cert_data.get("cert_type") or DEFAULT_CERT_TYPE).lower()

    api = client.CustomObjectsApi()
    cert_secret_name = component_name + "-secret"
    cert_name = component_name + "-cert"
    cert_dir = external_cert_data.get("external_cert_directory") + "external/"
    custom_resource = create_certificate_object(ctx, cert_secret_name,
                                                external_cert_data,
                                                external_tls_config,
                                                cert_name, issuer)
    # Create the volumes
    if cert_type != 'pem':
        ctx.logger.info("Creating volume with passwords")
        password_secret_name, password_secret_key = create_secret_with_password(namespace, component_name + "-cert-password", "password",  30)
        deployment_description["secrets"].append(password_secret_name)
        custom_resource.get("spec")["keystores"] = _create_keystores_object(_get_keystores_object_type(cert_type), password_secret_name)
        projected_volume_sources = _create_projected_volume_with_password(
            cert_type, cert_secret_name, password_secret_name, password_secret_key)
    else:
        ctx.logger.info("Creating PEM volume")
        projected_volume_sources = _create_pem_projected_volume(cert_secret_name)

    # Create the volume mounts
    projected_volume = client.V1ProjectedVolumeSource(sources=projected_volume_sources)
    volumes.append(client.V1Volume(name="certmanager-certs-volume", projected=projected_volume))
    volume_mounts.append(client.V1VolumeMount(name="certmanager-certs-volume", mount_path=cert_dir))

    #Create certificate custom resource
    ctx.logger.info("Certificate CRD: " + str(custom_resource))
    api.create_namespaced_custom_object(
        group="cert-manager.io",
        version="v1",
        namespace=namespace,
        plural="certificates",
        body=custom_resource
    )
    deployment_description["certificates"].append(cert_name)
    deployment_description["secrets"].append(cert_secret_name)
    ctx.logger.info("CRD certificate created")


def deploy(ctx, namespace, component_name, image, replicas, always_pull, k8sconfig, **kwargs):
    """
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
        - tls: a dictionary of TLS-related information:
            "cert_path": mount point for certificate volume in init container
            "image": Docker image to use for TLS init container
            "component_cert_dir" : default mount point for certs
        - cert_post_processor: a dictionary of cert_post_processor information:
            "image_tag": docker image to use for cert-post-processor init container
    kwargs may have:
        - volumes:  array of volume objects, where a volume object is:
            {"host":{"path": "/path/on/host"}, "container":{"bind":"/path/on/container","mode":"rw_or_ro"}
        - ports: array of strings in the form "container_port:host_port"
        - env: map of name-value pairs ( {name0: value0, name1: value1...}
        - log_info: an object with info for setting up ELK logging, with the form:
            {"log_directory": "/path/to/container/log/directory", "alternate_fb_path" : "/alternate/sidecar/log/path"}
        - tls_info: an object with info for setting up TLS (HTTPS), with the form:
            {"use_tls": true, "cert_directory": "/path/to/container/cert/directory" }
        - external_cert: an object with information for setting up the init container for external certificates creation, with the form:
            {"external_cert":
                "external_cert_directory": "/path/to/directory_where_certs_should_be_placed",
                "use_external_tls": true or false,
                "ca_name": "ca-name-value",
                "cert_type": "P12" or "JKS" or "PEM",
                "external_certificate_parameters":
                    "common_name": "common-name-value",
                    "sans": "sans-value"}
        - labels: dict with label-name/label-value pairs, e.g. {"cfydeployment" : "lsdfkladflksdfsjkl", "cfynode":"mycomponent"}
            These label will be set on all the pods deployed as a result of this deploy() invocation.
        - resources: dict with optional "limits" and "requests" resource requirements, each a dict containing:
            - cpu:    number CPU usage, like 0.5
            - memory: string memory requirement, like "2Gi"
        - readiness: dict with health check info; if present, used to create a readiness probe for the main container.  Includes:
            - type: check is done by making http(s) request to an endpoint ("http", "https") or by exec'ing a script in the container ("script", "docker")
            - interval: period (in seconds) between probes
            - timeout:  time (in seconds) to allow a probe to complete
            - endpoint: the path portion of the URL that points to the readiness endpoint for "http" and "https" types
            - path: the full path to the script to be executed in the container for "script" and "docker" types
        - liveness: dict with health check info; if present, used to create a liveness probe for the main container.  Includes:
            - type: check is done by making http(s) request to an endpoint ("http", "https") or by exec'ing a script in the container ("script", "docker")
            - interval: period (in seconds) between probes
            - timeout:  time (in seconds) to allow a probe to complete
            - endpoint: the path portion of the URL that points to the liveness endpoint for "http" and "https" types
            - path: the full path to the script to be executed in the container for "script" and "docker" types
        - k8s_location: name of the Kubernetes location (cluster) where the component is to be deployed

    """

    deployment_ok = False
    cip_service_created = False
    deployment_description = {
        "namespace": namespace,
        "location": kwargs.get("k8s_location"),
        "deployment": '',
        "services": [],
        "certificates": [],
        "secrets": []
    }

    try:

        # Get API handles
        _configure_api(kwargs.get("k8s_location"))
        core = client.CoreV1Api()
        k8s_apps_v1_api_client = client.AppsV1Api()

        # Parse the port mapping
        container_ports, port_map = parse_ports(kwargs.get("ports", []))

        # Parse the volumes list into volumes and volume_mounts for the deployment
        volumes, volume_mounts = _parse_volumes(kwargs.get("volumes", []))

        # Initialize the list of containers that will be part of the pod
        containers = []
        init_containers = []

        # Set up the ELK logging sidecar container, if needed
        _add_elk_logging_sidecar(containers, volumes, volume_mounts, component_name, kwargs.get("log_info"),
                                 k8sconfig.get("filebeat"))

        # Set up TLS information
        _add_tls_init_container(ctx, init_containers, volumes, volume_mounts, kwargs.get("tls_info") or {},
                                k8sconfig.get("tls"))

        # Set up external TLS information
        external_cert = kwargs.get("external_cert")
        cmpv2_issuer_config = k8sconfig.get("cmpv2_issuer")
        ctx.logger.info("CMPv2 Issuer properties: " + str(cmpv2_issuer_config))

        cmpv2_integration_enabled = bool(util.strtobool(cmpv2_issuer_config.get("enabled")))
        ctx.logger.info("CMPv2 integration enabled: " + str(cmpv2_integration_enabled))


        if external_cert and external_cert.get("use_external_tls"):
            if cmpv2_integration_enabled:
                _create_certificate_custom_resource(ctx, external_cert,
                                                   k8sconfig.get("external_cert"),
                                                   cmpv2_issuer_config.get("name"),
                                                   namespace,
                                                   component_name, volumes,
                                                   volume_mounts, deployment_description)
            else:
                _add_external_tls_init_container(ctx, init_containers, volumes, external_cert,
                                                 k8sconfig.get("external_cert"))
            _add_cert_post_processor_init_container(ctx, init_containers, kwargs.get("tls_info") or {},
                                                        k8sconfig.get("tls"), external_cert,
                                                        k8sconfig.get(
                                                            "cert_post_processor"),cmpv2_integration_enabled)

        # Create the container for the component
        # Make it the first container in the pod
        container_args = {key: kwargs.get(key) for key in ("env", "readiness", "liveness", "resources")}
        container_args['container_ports'] = container_ports
        container_args['volume_mounts'] = volume_mounts
        containers.insert(0, _create_container_object(component_name, image, always_pull, **container_args))

        # Build the k8s Deployment object
        labels = kwargs.get("labels", {})
        labels["app"] = component_name
        dep = _create_deployment_object(component_name, containers, init_containers, replicas, volumes, labels,
                                        pull_secrets=k8sconfig["image_pull_secrets"])

        # Have k8s deploy it
        k8s_apps_v1_api_client.create_namespaced_deployment(namespace, dep)
        deployment_ok = True
        deployment_description["deployment"] = _create_deployment_name(component_name)

        # Create service(s), if a port mapping is specified
        if port_map:
            service_ports, exposed_ports, exposed_ports_ipv6 = _process_port_map(port_map)

            # Create a ClusterIP service for access via the k8s network
            service = _create_service_object(_create_service_name(component_name), component_name, service_ports, None,
                                             labels, "ClusterIP", "IPv4")
            core.create_namespaced_service(namespace, service)
            cip_service_created = True
            deployment_description["services"].append(_create_service_name(component_name))

            # If there are ports to be exposed on the k8s nodes, create a "NodePort" service
            if exposed_ports:
                exposed_service = \
                    _create_service_object(_create_exposed_service_name(component_name), component_name, exposed_ports,
                                           '', labels, "NodePort", "IPv4")
                core.create_namespaced_service(namespace, exposed_service)
                deployment_description["services"].append(_create_exposed_service_name(component_name))

            if exposed_ports_ipv6:
                exposed_service_ipv6 = \
                    _create_service_object(_create_exposed_v6_service_name(component_name), component_name,
                                           exposed_ports_ipv6, '', labels, "NodePort", "IPv6")
                core.create_namespaced_service(namespace, exposed_service_ipv6)
                deployment_description["services"].append(_create_exposed_v6_service_name(component_name))

    except Exception as e:
        # If the ClusterIP service was created, delete the service:
        if cip_service_created:
            core.delete_namespaced_service(_create_service_name(component_name), namespace)
        # If the deployment was created but not the service, delete the deployment
        if deployment_ok:
            client.AppsV1Api().delete_namespaced_deployment(_create_deployment_name(component_name), namespace,
                                                            body=client.V1DeleteOptions())
        raise e

    return dep, deployment_description


def undeploy(deployment_description):
    _configure_api(deployment_description["location"])

    namespace = deployment_description["namespace"]

    # remove any services associated with the component
    for service in deployment_description["services"]:
        client.CoreV1Api().delete_namespaced_service(service, namespace)

    for secret in deployment_description["secrets"]:
        client.CoreV1Api().delete_namespaced_secret(secret, namespace)

    for cert in deployment_description["certificates"]:
        # client.CoreV1Api().delete_namespaced_service(service, namespace)
        client.CustomObjectsApi().delete_namespaced_custom_object(
            group="cert-manager.io",
            version="v1",
            name=cert,
            namespace=namespace,
            plural="certificates"
        )
    # Have k8s delete the underlying pods and replicaset when deleting the deployment.
    options = client.V1DeleteOptions(propagation_policy="Foreground")
    client.AppsV1Api().delete_namespaced_deployment(deployment_description["deployment"], namespace, body=options)


def is_available(location, namespace, component_name):
    _configure_api(location)
    dep_status = client.AppsV1Api().read_namespaced_deployment_status(_create_deployment_name(component_name),
                                                                      namespace)
    # Check if the number of available replicas is equal to the number requested and that the replicas match the
    # current spec This check can be used to verify completion of an initial deployment, a scale operation,
    # or an update operation
    return dep_status.status.available_replicas == dep_status.spec.replicas and dep_status.status.updated_replicas == dep_status.spec.replicas


def scale(deployment_description, replicas):
    """ Trigger a scaling operation by updating the replica count for the Deployment """

    def update_replica_count(spec):
        spec.spec.replicas = replicas
        return spec

    _patch_deployment(deployment_description["location"], deployment_description["namespace"],
                      deployment_description["deployment"], update_replica_count)


def upgrade(deployment_description, image, container_index=0):
    """ Trigger a rolling upgrade by sending a new image name/tag to k8s """

    def update_image(spec):
        spec.spec.template.spec.containers[container_index].image = image
        return spec

    _patch_deployment(deployment_description["location"], deployment_description["namespace"],
                      deployment_description["deployment"], update_image)


def rollback(deployment_description, rollback_to=0):
    """
    Undo upgrade by rolling back to a previous revision of the deployment.
    By default, go back one revision.
    rollback_to can be used to supply a specific revision number.
    Returns the image for the app container and the replica count from the rolled-back deployment
    """
    '''
    2018-07-13
    Currently this does not work due to a bug in the create_namespaced_deployment_rollback() method.
    The k8s python client code throws an exception while processing the response from the API.
    See:
       - https://github.com/kubernetes-client/python/issues/491
       - https://github.com/kubernetes/kubernetes/pull/63837
    The fix has been merged into the master branch but is not in the latest release.
    '''
    _configure_api(deployment_description["location"])
    deployment = deployment_description["deployment"]
    namespace = deployment_description["namespace"]

    # Initiate the rollback
    client.ExtensionsV1beta1Api().create_namespaced_deployment_rollback(
        deployment,
        namespace,
        client.AppsV1beta1DeploymentRollback(name=deployment,
                                             rollback_to=client.AppsV1beta1RollbackConfig(revision=rollback_to)))

    # Read back the spec for the rolled-back deployment
    spec = client.AppsV1Api().read_namespaced_deployment(deployment, namespace)
    return spec.spec.template.spec.containers[0].image, spec.spec.replicas


def execute_command_in_deployment(deployment_description, command):
    """
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
    """
    location = deployment_description["location"]
    _configure_api(location)
    deployment = deployment_description["deployment"]
    namespace = deployment_description["namespace"]

    # Get names of all the running pods belonging to the deployment
    pod_names = [pod.metadata.name for pod in client.CoreV1Api().list_namespaced_pod(
        namespace=namespace,
        label_selector="k8sdeployment={0}".format(deployment),
        field_selector="status.phase=Running"
    ).items]

    # Execute command in the running pods
    return [_execute_command_in_pod(location, namespace, pod_name, command)
            for pod_name in pod_names]




