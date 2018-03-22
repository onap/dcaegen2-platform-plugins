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
import uuid
from msb import msb
from kubernetes import config, client

def _create_deployment_name(component_name):
    return "dep-{0}".format(component_name)

def _create_service_name(component_name):
    return "{0}".format(component_name)

def _create_exposed_service_name(component_name):
    return ("x{0}".format(component_name))[:63]

def _configure_api():
    #TODO: real configuration
    config.load_kube_config(os.path.join(os.environ["HOME"], '.kube/config'))

def _create_container_object(name, image, always_pull, env={}, container_ports=[], volume_mounts = []):
    # Set up environment variables
    # Copy any passed in environment variables
    env_vars = [client.V1EnvVar(name=k, value=env[k]) for k in env.keys()]
    # Add POD_IP with the IP address of the pod running the container
    pod_ip = client.V1EnvVarSource(field_ref = client.V1ObjectFieldSelector(field_path="status.podIP"))
    env_vars.append(client.V1EnvVar(name="POD_IP",value_from=pod_ip))

    # Define container for pod
    return client.V1Container(
        name=name,
        image=image,
        image_pull_policy='Always' if always_pull else 'IfNotPresent',
        env=env_vars,
        ports=[client.V1ContainerPort(container_port=p) for p in container_ports],
        volume_mounts = volume_mounts
    )

def _create_deployment_object(component_name,
                              containers,
                              replicas,
                              volumes,
                              labels, 
                              pull_secrets=[]):

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
        metadata=client.V1ObjectMeta(name=_create_deployment_name(component_name)),
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
    kwargs may have:
        - volumes:  array of volume objects, where a volume object is:
            {"host":{"path": "/path/on/host"}, "container":{"bind":"/path/on/container","mode":"rw_or_ro"}
        - ports: array of strings in the form "container_port:host_port"
        - env: map of name-value pairs ( {name0: value0, name1: value1...}
        - msb_list: array of msb objects, where an msb object is as described in msb/msb.py.
        - log_info: an object with info for setting up ELK logging, with the form:
            {"log_directory": "/path/to/container/log/directory", "alternate_fb_path" : "/alternate/sidecar/log/path"}
        - labels: dict with label-name/label-value pairs, e.g. {"cfydeployment" : "lsdfkladflksdfsjkl", "cfynode":"mycomponent"}
            These label will be set on all the pods deployed as a result of this deploy() invocation.

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
            containers.append(_create_container_object("filebeat", fb["image"], False, {}, [], sidecar_volume_mounts))

            # Create the volume for the sidecar configuration data and the volume mount for it
            # The configuration data is in a k8s ConfigMap that should be created when DCAE is installed.
            volumes.append(
                client.V1Volume(name="filebeat-conf", config_map=client.V1ConfigMapVolumeSource(name=fb["config_map"])))
            sidecar_volume_mounts.append(
                client.V1VolumeMount(name="filebeat-conf", mount_path=fb["config_path"], sub_path=fb["config_subpath"]))

        # Create the container for the component
        # Make it the first container in the pod
        containers.insert(0, _create_container_object(component_name, image, always_pull, kwargs.get("env", {}), container_ports, volume_mounts))

        # Build the k8s Deployment object
        labels = kwargs.get("labels", {})
        labels.update({"app": component_name})
        dep = _create_deployment_object(component_name, containers, replicas, volumes, labels, pull_secrets=k8sconfig["image_pull_secrets"])

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
    # TODO: do real configuration
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
    # Check if the number of available replicas is equal to the number requested
    return dep_status.status.available_replicas >= dep_status.spec.replicas

def scale(deployment_description, replicas):
    # TODO: do real configuration
    _configure_api()

    namespace = deployment_description["namespace"]
    name = deployment_description["deployment"]

    # Get deployment spec
    spec = client.ExtensionsV1beta1Api().read_namespaced_deployment(name, namespace)

    # Update the replica count in the spec
    spec.spec.replicas = replicas
    client.ExtensionsV1beta1Api().patch_namespaced_deployment(name, namespace, spec)

