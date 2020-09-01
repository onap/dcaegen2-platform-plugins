# ============LICENSE_START=======================================================
# org.onap.dcae
# ================================================================================
# Copyright (c) 2019-2020 AT&T Intellectual Property. All rights reserved.
# Copyright (c) 2020 Pantheon.tech. All rights reserved.
# Copyright (c) 2020 Nokia. All rights reserved.
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
        "external_cert": {
            "image_tag": "repo/aaf-certservice-client:1.2.3",
            "request_url" : "https://request:1010/url",
            "timeout" : "30000",
            "country" : "US",
            "organization" : "Linux-Foundation",
            "state" : "California",
            "organizational_unit" : "ONAP",
            "location" : "San-Francisco",
            "keystore_password" : "secret1",
            "truststore_password" : "secret2"
        },
        "truststore_merger": {
            "image_tag": "repo/oom-truststore-merger:1.2.3"
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

def verify_external_cert(dep):
    cert_container = dep.spec.template.spec.init_containers[1]
    print(cert_container)
    assert cert_container.image == "repo/aaf-certservice-client:1.2.3"
    assert cert_container.name == "cert-service-client"
    assert len(cert_container.volume_mounts) == 2
    assert cert_container.volume_mounts[0].name == "tls-info"
    assert cert_container.volume_mounts[0].mount_path == "/path/to/container/cert/directory/"
    assert cert_container.volume_mounts[1].name == "tls-volume"
    assert cert_container.volume_mounts[1].mount_path == "/etc/onap/aaf/certservice/certs/"

    expected_envs = {
            "REQUEST_URL": "https://request:1010/url",
            "REQUEST_TIMEOUT": "30000",
            "OUTPUT_PATH": "/path/to/container/cert/directory/external",
            "OUTPUT_TYPE": "P12",
            "CA_NAME": "myname",
            "COMMON_NAME": "mycommonname",
            "ORGANIZATION": "Linux-Foundation",
            "ORGANIZATION_UNIT": "ONAP",
            "LOCATION": "San-Francisco",
            "STATE": "California",
            "COUNTRY": "US",
            "SANS": "mysans",
            "KEYSTORE_PATH": "/etc/onap/aaf/certservice/certs/certServiceClient-keystore.jks",
            "KEYSTORE_PASSWORD": "secret1",
            "TRUSTSTORE_PATH": "/etc/onap/aaf/certservice/certs/truststore.jks",
            "TRUSTSTORE_PASSWORD": "secret2"}

    envs = {k.name: k.value for k in cert_container.env}
    for k in expected_envs:
        assert (k in envs and expected_envs[k] == envs[k])

def verify_truststore_merger(dep):
    cert_container = dep.spec.template.spec.init_containers[2]
    print(cert_container)
    assert cert_container.image == "repo/oom-truststore-merger:1.2.3"
    assert cert_container.name == "truststore-merger"
    assert len(cert_container.volume_mounts) == 1
    assert cert_container.volume_mounts[0].name == "tls-info"
    assert cert_container.volume_mounts[0].mount_path == "/opt/dcae/cacert/"

    expected_envs = {
        "TRUSTSTORES_PATHS": "/opt/dcae/cacert/trust.jks:/opt/dcae/cacert/external/truststore.p12",
        "TRUSTSTORES_PASSWORDS_PATHS": "/opt/dcae/cacert/trust.pass:/opt/dcae/cacert/external/truststore.pass",
        "KEYSTORE_SOURCE_PATHS": "/opt/dcae/cacert/external/keystore.p12:/opt/dcae/cacert/external/keystore.pass",
        "KEYSTORE_DESTINATION_PATHS":  "/opt/dcae/cacert/cert.p12:/opt/dcae/cacert/p12.pass"
    }

    envs = {k.name: k.value for k in cert_container.env}
    for k in expected_envs:
        assert (k in envs and expected_envs[k] == envs[k])


def do_deploy(tls_info=None):
    ''' Common deployment operations '''
    import k8sclient.k8sclient

    k8s_test_config = _set_k8s_configuration()

    kwargs = _set_common_kwargs()
    kwargs['resources'] = _set_resources()

    if tls_info:
        kwargs["tls_info"] = tls_info

    dep, deployment_description = k8sclient.k8sclient.deploy(k8s_ctx(), "k8stest", "testcomponent", "example.com/testcomponent:1.4.3", 1, False, k8s_test_config, **kwargs)

    # Make sure all of the basic k8s parameters are correct
    verify_common(dep, deployment_description)

    return dep, deployment_description


def do_deploy_ext(ext_tls_info):
    ''' Common deployment operations '''
    import k8sclient.k8sclient

    k8s_test_config = _set_k8s_configuration()

    kwargs = _set_common_kwargs()
    kwargs['resources'] = _set_resources()
    kwargs["external_cert"] = ext_tls_info

    dep, deployment_description = k8sclient.k8sclient.deploy(k8s_ctx(), "k8stest", "testcomponent", "example.com/testcomponent:1.4.3", 1, False, k8s_test_config, **kwargs)

    # Make sure all of the basic k8s parameters are correct
    verify_common(dep, deployment_description)

    return dep, deployment_description

class k8s_logger:
    def info(self, text):
        print(text)

class k8s_ctx:
    logger = k8s_logger()


