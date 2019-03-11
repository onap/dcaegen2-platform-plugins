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

import pytest

def test_parse_interval():
    from k8sclient.k8sclient import _parse_interval

    good_intervals = [{"in": input, "ex": expected}
        for (input, expected) in [
            (30, 30),
            ("30", 30),
            ("30s", 30),
            ("2m", 2 * 60),
            ("2h", 2 * 60 * 60),
            ("24h", 24 * 60 * 60),
            (354123, 354123),
            ("354123", 354123),
            ("354123s", 354123),
            (1234567890123456789012345678901234567890L,1234567890123456789012345678901234567890L),
            ("1234567890123456789012345678901234567890",1234567890123456789012345678901234567890L),
            ("1234567890123456789012345678901234567890s",1234567890123456789012345678901234567890L),
            ("05s", 5),
            ("00000000000000000000000000000000005m", 5 * 60)
        ]
    ]

    bad_intervals = [
        -99,
        "-99",
        "-99s",
        "-99m",
        "-99h",
        "30d",
        "30w",
        "30y",
        "3 0s",
        "3 5m",
        30.0,
        "30.0s",
        "30.0m",
        "30.0h",
        "a 30s",
        "30s a",
        "a 30s a",
        "a 30",
        "30 a",
        "a 30 a",
        "i want an interval of 30s",
        "thirty seconds",
        "30 s",
        "30 m",
        "30 h",
        10E0,
        "10E0",
        3.14159,
        "3.14159s"
        "3:05",
        "3m05s",
        "3seconds",
        "3S",
        "1minute",
        "1stanbul"
    ]

    for test_case in good_intervals:
        assert _parse_interval(test_case["in"]) == test_case["ex"]

    for interval in bad_intervals:
        with pytest.raises(ValueError):
            _parse_interval(interval)

def test_parse_ports():
    from k8sclient.k8sclient import _parse_ports

    good_ports = [{"in": input, "ex": expected}
        for (input, expected) in [
            ("9101:0", (9101, 0, "TCP")),
            ("9101/TCP:0", (9101, 0, "TCP")),
            ("9101/tcp:0", (9101, 0, "TCP")),
            ("9101/UDP:0", (9101, 0, "UDP")),
            ("9101/udp:0", (9101, 0, "UDP")),
            ("9101:31043", (9101, 31043, "TCP")),
            ("9101/TCP:31043", (9101, 31043, "TCP")),
            ("9101/tcp:31043", (9101, 31043, "TCP")),
            ("9101/UDP:31043", (9101, 31043, "UDP")),
            ("9101/udp:31043", (9101, 31043, "UDP"))
        ]
    ]

    bad_ports = [
        "9101",
        "9101:",
        "9101:0x453",
        "9101:0/udp",
        "9101/:0",
        "9101/u:0",
        "9101/http:404",
        "9101:-1"
    ]

    port_list = [
        "9101:0",
        "5053/tcp:5053",
        "5053/udp:5053",
        "9661:19661",
        "9661/udp:19661",
        "8080/tcp:8080"
    ]

    expected_port_map = {
        (9101,"TCP") : 0,
        (5053,"TCP") : 5053,
        (5053,"UDP") : 5053,
        (9661,"TCP") : 19661,
        (9661,"UDP") : 19661,
        (8080,"TCP") : 8080
    }

    for test_case in good_ports:
        container_ports, port_map = _parse_ports([test_case["in"]])
        (cport, hport, proto) = test_case["ex"]
        assert container_ports == [(cport, proto)]
        assert port_map == {(cport, proto) : hport}

    for port in bad_ports:
        with pytest.raises(ValueError):
            _parse_ports([port])

    container_ports, port_map = _parse_ports(port_list)
    assert port_map == expected_port_map

def test_create_container():
    from k8sclient.k8sclient import _create_container_object
    from kubernetes import client

    container = _create_container_object("c1","nginx",False, container_ports=[(80, "TCP"), (53, "UDP")])

    assert container.ports[0].container_port == 80 and container.ports[0].protocol == "TCP"
    assert container.ports[1].container_port == 53 and container.ports[1].protocol == "UDP"

def test_create_probe():
    from k8sclient.k8sclient import _create_probe
    from kubernetes import client

    http_checks = [
        {"type" : "http", "endpoint" : "/example/health"}
    ]

    script_checks = [
        {"type" : "docker", "script": "/opt/app/health_check.sh"}
    ]

    for hc in http_checks:
        probe = _create_probe(hc, 13131)
        assert probe.http_get.path == hc["endpoint"]
        assert probe.http_get.scheme == hc["type"].upper()

    for hc in script_checks:
        probe = _create_probe(hc, 13131)
        assert probe._exec.command[0] == hc["script"]

def test_deploy(monkeypatch):
    import k8sclient.k8sclient
    from kubernetes import client

    # We need to patch the kubernetes 'client' module
    # Awkward because of the way it requires a function call
    # to get an API object
    core = client.CoreV1Api()
    ext = client.ExtensionsV1beta1Api()

    def pseudo_deploy(namespace, dep):
        return dep

    def pseudo_service(namespace, svc):
        return svc

    # patched_core returns a CoreV1Api object with the
    # create_namespaced_service method stubbed out so that there
    # is no attempt to call the k8s API server
    def patched_core():
        monkeypatch.setattr(core, "create_namespaced_service", pseudo_service)
        return core

    # patched_ext returns an ExtensionsV1beta1Api object with the
    # create_namespaced_deployment method stubbed out so that there
    # is no attempt to call the k8s API server
    def patched_ext():
        monkeypatch.setattr(ext,"create_namespaced_deployment", pseudo_deploy)
        return ext

    def pseudo_configure(loc):
        pass

    monkeypatch.setattr(k8sclient.k8sclient,"_configure_api", pseudo_configure)
    monkeypatch.setattr(client, "CoreV1Api", patched_core)
    monkeypatch.setattr(client,"ExtensionsV1beta1Api", patched_ext)

    k8s_test_config = {
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
            "image": "tlsrepo/tls-init-container:1.2.3"
        }
    }

    resources = {
        "limits": {
            "cpu" : 0.5,
            "memory" : "2Gi"
        },
        "requests": {
            "cpu" : 0.5,
            "memory" : "2Gi"
        }
    }

    kwargs = {
        "volumes": [
            {"host":{"path": "/path/on/host"}, "container":{"bind":"/path/on/container","mode":"rw"}}
        ],
        "ports": ["80:0", "443:0"],
        "env": {"name0": "value0", "name1": "value1"},
        "log_info": {"log_directory": "/path/to/container/log/directory"},
        "tls_info": {"use_tls": True, "cert_directory": "/path/to/container/cert/directory" },
        "readiness": {"type": "http", "endpoint" : "/ready"}
    }
    dep, deployment_description = k8sclient.k8sclient.deploy("k8stest","testcomponent","example.com/testcomponent:1.4.3",1,False, k8s_test_config, resources, **kwargs)

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
    assert app_container.volume_mounts[2].mount_path == "/path/to/container/cert/directory"

    # Needs to be correctly labeled so that the Service can find it
    assert dep.spec.template.metadata.labels["app"] == "testcomponent"
