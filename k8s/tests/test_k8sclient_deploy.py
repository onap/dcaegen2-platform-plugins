# ============LICENSE_START=======================================================
# org.onap.dcae
# ================================================================================
# Copyright (c) 2018-2020 AT&T Intellectual Property. All rights reserved.
# Copyright (c) 2020-2021 Nokia. All rights reserved.
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

# Test k8sclient deployment functions
# Verify that for a given configuration and set of inputs, k8sclient generates the proper
# Kubernetes entities
import pytest
from common import do_deploy, verify_ports, verify_image, verify_rediness_probe, verify_volumes, \
    verify_logs, verify_env_variables, verify_deployment_desc, verify_label
from common import verify_external_cert
from common import verify_cert_post_processor

K8S_CONFIGURATION = {
    "image_pull_secrets": ["secret0", "secret1"],
    "filebeat": {
        "log_path": "/var/log/onap",
        "data_path": "/usr/share/filebeat/data",
        "config_path": "/usr/share/filebeat/filebeat.yml",
        "config_subpath": "filebeat.yml",
        "image": "filebeat-repo/filebeat:latest",
        "config_map": "dcae-filebeat-configmap"
    },
    "tls": {
        "cert_path": "/opt/certs",
        "image": "tlsrepo/tls-init-container:1.2.3",
        "component_cert_dir": "/opt/dcae/cacert"
    },
    "external_cert": {
        "image_tag": "repo/oom-certservice-client:2.1.0",
        "request_url": "https://request:1010/url",
        "timeout": "30000",
        "country": "US",
        "organization": "Linux-Foundation",
        "state": "California",
        "organizational_unit": "ONAP",
        "location": "San-Francisco",
        "cert_secret_name": "oom-cert-service-client-tls-secret",
        "keystore_secret_key" : "keystore.jks",
        "truststore_secret_key" : "truststore.jks",
        "password_secret_name": "oom-cert-service-client-tls-secret-password",
        "keystore_password_secret_key" : "password",
        "truststore_password_secret_key" : "password"
    },
    "cert_post_processor": {
        "image_tag": "repo/oom-cert-post-processor:2.1.0"
    },
    "cbs": {
        "base_url": "https://config-binding-service:10443/service_component_all/test-component"
    },
    "cmpv2_issuer": {
        "enabled": "false",
        "name":    "cmpv2-issuer-onap"
    }
}

BASIC_KWARGS = {
    "volumes": [
        {
            "host": {
                "path": "/path/on/host"
            },
            "container": {
                "bind": "/path/on/container",
                "mode": "rw"
            }
        }
    ],
    "ports": [
        "80:0",
        "443:0"
    ],
    "env": {
        "NAME0": "value0",
        "NAME1": "value1"
    },
    "log_info": {
        "log_directory": "/path/to/container/log/directory"
    },
    "readiness": {
        "type": "http",
        "endpoint": "/ready"
    },
    "resources": {
        "limits": {
            "cpu": 0.5,
            "memory": "2Gi"
        },
        "requests": {
            "cpu": 0.5,
            "memory": "2Gi"
        }
    }
}

KWARGS_WITH_FULL_TLS = {"tls_info": {"use_tls": True, "cert_directory": "/path/to/container/cert/directory"}}
KWARGS_TLS_OFF = {"tls_info": {"use_tls": False, "cert_directory": "/path/to/container/cert/directory"}}
KWARGS_WITH_EXTERNAL_CERT = {"external_cert": {"external_cert_directory": "/path/to/container/cert/directory/",
                                               "use_external_tls": True,
                                               "cert_type": "P12",
                                               "ca_name": "myname",
                                               "external_certificate_parameters": {
                                                   "common_name": "mycommonname",
                                                   "sans": "mysans"}
                                               }}

KWARGS_WITH_CONFIG_MAP = {"config_volume": {"name": "myConfigMap"},
                          "container": {"bind": "/path/to/configMap", "mode": "ro"}}


test_data = [(KWARGS_WITH_EXTERNAL_CERT, "/opt/dcae/cacert"),
             (BASIC_KWARGS, "/opt/dcae/cacert"),
             (KWARGS_TLS_OFF, "/path/to/container/cert/directory"),
             (KWARGS_WITH_FULL_TLS, "/path/to/container/cert/directory")]


@pytest.mark.parametrize("blueprint_dict, path", test_data)
def test_deploy(mockk8sapi, blueprint_dict, path):
    # given
    kwargs = dict(BASIC_KWARGS)
    kwargs.update(blueprint_dict)

    # when
    dep, deployment_description = do_deploy(K8S_CONFIGURATION, kwargs)
    app_container = dep.spec.template.spec.containers[0]
    log_container = dep.spec.template.spec.containers[1]

    # then
    verify_label(dep)
    assert app_container.volume_mounts[2].mount_path == path
    verify_ports(app_container)
    verify_image(app_container)
    verify_rediness_probe(app_container)
    verify_volumes(app_container)
    verify_logs(log_container)
    verify_env_variables(app_container)
    verify_deployment_desc(deployment_description)


def test_deploy_external_cert(mockk8sapi):
    """ Deploy component with external TLS configuration """
    # given
    kwargs = dict(BASIC_KWARGS)
    kwargs.update(KWARGS_WITH_EXTERNAL_CERT)

    # when
    dep, deployment_description = do_deploy(K8S_CONFIGURATION, kwargs)

    # then
    verify_external_cert(dep)
    verify_cert_post_processor(dep)


def test_deploy_config_map(mockk8sapi):
    """ Deploy component with configMap in volumes """
    # given
    kwargs = dict(BASIC_KWARGS)
    kwargs['volumes'].append(KWARGS_WITH_CONFIG_MAP)

    # when
    dep, deployment_description = do_deploy(K8S_CONFIGURATION, kwargs)
    app_container = dep.spec.template.spec.containers[0]

    # then
    assert app_container.volume_mounts[1].mount_path == "/path/to/configMap"
