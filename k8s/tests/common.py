# ============LICENSE_START=======================================================
# org.onap.dcae
# ================================================================================
# Copyright (c) 2019-2020 AT&T Intellectual Property. All rights reserved.
# Copyright (c) 2020 Pantheon.tech. All rights reserved.
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
import pytest


def _get_item_by_name(list, name):
    """ Search a list of k8s API objects with the specified name """
    for item in list:
        if item.name == name:
            return item
    return None


def check_env_var(env_list, name, value):
    e = _get_item_by_name(env_list, name)
    assert e and e.value == value


def verify_label(dep):
    assert dep.spec.template.metadata.labels["app"] == "testcomponent"


def verify_deployment_desc(deployment_description):
    assert deployment_description["deployment"] == "dep-testcomponent"
    assert deployment_description["namespace"] == "k8stest"
    assert deployment_description["services"][0] == "testcomponent"


def verify_env_variables(app_container):
    env = app_container.env
    check_env_var(env, "NAME0", "value0")
    check_env_var(env, "NAME1", "value1")


def verify_logs(log_container):
    assert log_container.image == "filebeat-repo/filebeat:latest"
    assert log_container.volume_mounts[0].mount_path == "/var/log/onap/testcomponent"
    assert log_container.volume_mounts[0].name == "component-log"
    assert log_container.volume_mounts[1].mount_path == "/usr/share/filebeat/data"
    assert log_container.volume_mounts[1].name == "filebeat-data"
    assert log_container.volume_mounts[2].mount_path == "/usr/share/filebeat/filebeat.yml"
    assert log_container.volume_mounts[2].name == "filebeat-conf"


def verify_volumes(app_container):
    assert len(app_container.volume_mounts) >= 2
    assert app_container.volume_mounts[0].mount_path == "/path/on/container"
    assert app_container.volume_mounts[-2].mount_path == "/path/to/container/log/directory"


def verify_rediness_probe(app_container):
    assert app_container.readiness_probe.http_get.path == "/ready"
    assert app_container.readiness_probe.http_get.scheme == "HTTP"


def verify_image(app_container):
    assert app_container.image == "example.com/testcomponent:1.4.3"
    assert app_container.image_pull_policy == "IfNotPresent"


def verify_ports(app_container):
    assert len(app_container.ports) == 2
    assert app_container.ports[0].container_port == 80
    assert app_container.ports[1].container_port == 443


def verify_external_cert(dep):
    cert_container = dep.spec.template.spec.init_containers[1]
    print(cert_container)
    assert cert_container.image == "repo/oom-certservice-client:2.1.0"
    assert cert_container.name == "cert-service-client"
    assert len(cert_container.volume_mounts) == 2
    assert cert_container.volume_mounts[0].name == "tls-info"
    assert cert_container.volume_mounts[0].mount_path == "/path/to/container/cert/directory/"
    assert cert_container.volume_mounts[1].name == "tls-volume"
    assert cert_container.volume_mounts[1].mount_path == "/etc/onap/oom/certservice/certs/"

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
        "KEYSTORE_PATH": "/etc/onap/oom/certservice/certs/keystore.jks",
        "TRUSTSTORE_PATH": "/etc/onap/oom/certservice/certs/truststore.jks"}


    envs = {k.name: k.value for k in cert_container.env}
    for k in expected_envs:
        assert (k in envs and expected_envs[k] == envs[k])

    envs_from_source = {k.name: k.value_from for k in cert_container.env}
    expected_secret_key_ref = {
        "KEYSTORE_PASSWORD": "oom-cert-service-client-tls-secret-password",
        "TRUSTSTORE_PASSWORD": "oom-cert-service-client-tls-secret-password"
    }
    for key, value in expected_secret_key_ref.items():
        assert (key in envs_from_source and str(envs_from_source[key]).__contains__(value))


def verify_cert_post_processor(dep):
    cert_container = dep.spec.template.spec.init_containers[2]
    print(cert_container)
    assert cert_container.image == "repo/oom-cert-post-processor:2.1.0"
    assert cert_container.name == "cert-post-processor"
    assert len(cert_container.volume_mounts) == 1
    assert cert_container.volume_mounts[0].name == "tls-info"
    assert cert_container.volume_mounts[0].mount_path == "/opt/dcae/cacert/"

    expected_envs = {
        "TRUSTSTORES_PATHS": "/opt/dcae/cacert/trust.jks:/opt/dcae/cacert/external/truststore.p12",
        "TRUSTSTORES_PASSWORDS_PATHS": "/opt/dcae/cacert/trust.pass:/opt/dcae/cacert/external/truststore.pass",
        "KEYSTORE_SOURCE_PATHS": "/opt/dcae/cacert/external/keystore.p12:/opt/dcae/cacert/external/keystore.pass",
        "KEYSTORE_DESTINATION_PATHS": "/opt/dcae/cacert/cert.p12:/opt/dcae/cacert/p12.pass"
    }

    envs = {k.name: k.value for k in cert_container.env}
    for k in expected_envs:
        assert (k in envs and expected_envs[k] == envs[k])


def do_deploy(k8s_test_config, kwargs):
    """ Common deployment operations """
    import k8sclient.k8sclient
    dep, deployment_description = k8sclient.k8sclient.deploy(k8s_ctx(), "k8stest", "testcomponent",
                                                             "example.com/testcomponent:1.4.3", 1, False,
                                                             k8s_test_config, **kwargs)

    return dep, deployment_description


class k8s_logger:
    def info(self, text):
        print(text)


class k8s_ctx:
    logger = k8s_logger()
