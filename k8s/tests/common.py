# ============LICENSE_START=======================================================
# org.onap.dcae
# ================================================================================
# Copyright (c) 2019 AT&T Intellectual Property. All rights reserved.
# Copyright (c) 2020 Pantheon.tech. All rights reserved.
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

# Common functions for unit testing
def _set_k8s_configuration():
    ''' Set up the basic k8s configuration '''
    return  {
        "image_pull_secrets" : ["secret0", "secret1"],
        "filebeat" : {
            "log_path": "/var/log/onap",
            "data_path": "/usr/share/filebeat/data",
            "config_path": "/usr/share/filebeat/filebeat.yml",
            "config_subpath": "filebeat.yml",
            "image" : "filebeat-repo/filebeat:latest",
            "config_map" : "dcae-filebeat-configmap"
        },
        "tls" : {
            "cert_path": "/opt/certs",
            "image": "tlsrepo/tls-init-container:1.2.3",
            "component_cert_dir": "/opt/dcae/cacert"
        },
        "cbs": {
            "base_url": "https://config-binding-service:10443/service_component_all/test-component"
        }
    }

def _set_resources():
    ''' Set resources '''
    return {
        "limits": {
            "cpu" : 0.5,
            "memory" : "2Gi"
        },
        "requests": {
            "cpu" : 0.5,
            "memory" : "2Gi"
        }
    }

def _set_common_kwargs():
    ''' Set kwargs common to all test cases '''
    return {
        "volumes": [
            {"host":{"path": "/path/on/host"}, "container":{"bind":"/path/on/container","mode":"rw"}}
        ],
        "ports": ["80:0", "443:0"],
        "env": {"NAME0": "value0", "NAME1": "value1"},
        "log_info": {"log_directory": "/path/to/container/log/directory"},
        "readiness": {"type": "http", "endpoint" : "/ready"}
    }

def _get_item_by_name(list, name):
    ''' Search a list of k8s API objects with the specified name '''
    for item in list:
        if item.name == name:
            return item
    return None

def check_env_var(env_list, name, value):
    e = _get_item_by_name(env_list, name)
    assert e and e.value == value

def verify_common(dep, deployment_description):
    ''' Check results common to all test cases '''
    assert deployment_description["deployment"] == "dep-testcomponent"
    assert deployment_description["namespace"] == "k8stest"
    assert deployment_description["services"][0] == "testcomponent"

    # For unit test purposes, we want to make sure that the deployment object
    # we're passing to the k8s API is correct
    app_container = dep.spec.template.spec.containers[0]
    assert app_container.image == "example.com/testcomponent:1.4.3"
    assert app_container.image_pull_policy == "IfNotPresent"
    assert len(app_container.ports) == 2
    assert app_container.ports[0].container_port == 80
    assert app_container.ports[1].container_port == 443
    assert app_container.readiness_probe.http_get.path == "/ready"
    assert app_container.readiness_probe.http_get.scheme == "HTTP"
    assert len(app_container.volume_mounts) == 3
    assert app_container.volume_mounts[0].mount_path == "/path/on/container"
    assert app_container.volume_mounts[1].mount_path == "/path/to/container/log/directory"

    # Check environment variables
    env = app_container.env
    check_env_var(env, "NAME0", "value0")
    check_env_var(env, "NAME1", "value1")

    # Should have a log container with volume mounts
    log_container = dep.spec.template.spec.containers[1]
    assert log_container.image == "filebeat-repo/filebeat:latest"
    assert log_container.volume_mounts[0].mount_path == "/var/log/onap/testcomponent"
    assert log_container.volume_mounts[0].name == "component-log"
    assert log_container.volume_mounts[1].mount_path == "/usr/share/filebeat/data"
    assert log_container.volume_mounts[1].name == "filebeat-data"
    assert log_container.volume_mounts[2].mount_path == "/usr/share/filebeat/filebeat.yml"
    assert log_container.volume_mounts[2].name == "filebeat-conf"

    # Needs to be correctly labeled so that the Service can find it
    assert dep.spec.template.metadata.labels["app"] == "testcomponent"


def do_deploy(tls_info=None):
    ''' Common deployment operations '''
    import k8sclient.k8sclient

    k8s_test_config = _set_k8s_configuration()

    kwargs = _set_common_kwargs()
    kwargs['resources'] = _set_resources()

    if tls_info:
        kwargs["tls_info"] = tls_info

    dep, deployment_description = k8sclient.k8sclient.deploy("k8stest", "testcomponent", "example.com/testcomponent:1.4.3", 1, False, k8s_test_config, **kwargs)

    # Make sure all of the basic k8s parameters are correct
    verify_common(dep, deployment_description)

    return dep, deployment_description
