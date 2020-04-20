# ============LICENSE_START=======================================================
# org.onap.dcae
# ================================================================================
# Copyright (c) 2017-2019 AT&T Intellectual Property. All rights reserved.
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

import copy
import pytest
from cloudify.exceptions import NonRecoverableError, RecoverableError


def test_generate_component_name(mockconfig):
    from k8splugin import tasks
    kwargs = { "service_component_type": "doodle",
            "service_component_name_override": None }

    assert "doodle" in tasks._generate_component_name(**kwargs)["name"]

    kwargs["service_component_name_override"] = "yankee"

    assert "yankee" == tasks._generate_component_name(**kwargs)["name"]


def test_parse_streams(monkeypatch, mockconfig):
    import k8splugin
    from k8splugin import tasks
    # Good case for streams_publishes
    test_input = { "streams_publishes": [{"name": "topic00", "type": "message_router"},
            {"name": "feed00", "type": "data_router"}],
            "streams_subscribes": {} }

    expected = {'feed00': {'type': 'data_router', 'name': 'feed00'},
            'streams_publishes': [{'type': 'message_router', 'name': 'topic00'},
                {'type': 'data_router', 'name': 'feed00'}],
            'streams_subscribes': {},
            'topic00': {'type': 'message_router', 'name': 'topic00'}
            }

    assert expected == tasks._parse_streams(**test_input)

    # Good case for streams_subscribes (password provided)
    test_input = { "ports": ["1919:0", "1920:0"],"name": "testcomponent",
            "streams_publishes": {},
            "streams_subscribes": [{"name": "topic01", "type": "message_router"},
                {"name": "feed01", "type": "data_router", "username": "hero",
                    "password": "123456", "route":"test/v0"}] }

    expected = {'ports': ['1919:0', '1920:0'], 'name': 'testcomponent',
                'feed01': {'type': 'data_router', 'name': 'feed01',
                    'username': 'hero', 'password': '123456', 'route': 'test/v0', 'delivery_url':'http://testcomponent:1919/test/v0'},
                'streams_publishes': {},
                'streams_subscribes': [{'type': 'message_router', 'name': 'topic01'},
                {'type': 'data_router', 'name': 'feed01', 'username': 'hero',
                    'password': '123456', 'route':'test/v0'}],
                'topic01': {'type': 'message_router', 'name': 'topic01'}}

    assert expected == tasks._parse_streams(**test_input)

    # Good case for streams_subscribes (password generated)
    test_input = { "ports": ["1919:0", "1920:0"],"name": "testcomponent",
        "streams_publishes": {},
        "streams_subscribes": [{"name": "topic01", "type": "message_router"},
                {"name": "feed01", "type": "data_router", "username": None,
                    "password": None, "route": "test/v0"}] }

    def not_so_random(n):
        return "nosurprise"

    monkeypatch.setattr(k8splugin.utils, "random_string", not_so_random)

    expected = { 'ports': ['1919:0', '1920:0'], 'name': 'testcomponent',
             'feed01': {'type': 'data_router', 'name': 'feed01',
                    'username': 'nosurprise', 'password': 'nosurprise', 'route':'test/v0', 'delivery_url':'http://testcomponent:1919/test/v0'},
            'streams_publishes': {},
            'streams_subscribes': [{'type': 'message_router', 'name': 'topic01'},
                {'type': 'data_router', 'name': 'feed01', 'username': None,
                    'password': None, 'route': 'test/v0'}],
            'topic01': {'type': 'message_router', 'name': 'topic01'}}

    assert expected == tasks._parse_streams(**test_input)


def test_setup_for_discovery(monkeypatch, mockconfig):
    import k8splugin
    from k8splugin import tasks

    test_input = { "name": "some-name",
            "application_config": { "one": "a", "two": "b" } }

    def fake_push_config(conn, name, application_config):
        return

    monkeypatch.setattr(k8splugin.discovery, "push_service_component_config",
            fake_push_config)

    assert test_input == tasks._setup_for_discovery(**test_input)

    def fake_push_config_connection_error(conn, name, application_config):
        raise k8splugin.discovery.DiscoveryConnectionError("Boom")

    monkeypatch.setattr(k8splugin.discovery, "push_service_component_config",
            fake_push_config_connection_error)

    with pytest.raises(RecoverableError):
        tasks._setup_for_discovery(**test_input)

def test_verify_container(monkeypatch, mockconfig):
    import k8sclient
    from k8splugin import tasks
    from k8splugin.exceptions import DockerPluginDeploymentError

    def fake_is_available_success(loc, ch, scn):
        return True

    monkeypatch.setattr(k8sclient, "is_available",
            fake_is_available_success)

    assert tasks._verify_k8s_deployment("some-location","some-name", 3)

    def fake_is_available_never_good(loc, ch, scn):
        return False

    monkeypatch.setattr(k8sclient, "is_available",
            fake_is_available_never_good)

    assert not tasks._verify_k8s_deployment("some-location", "some-name", 2)

def test_enhance_docker_params(mockconfig):
    from k8splugin import tasks
    # Good - Test empty docker config

    test_kwargs = { "docker_config": {}, "service_id": None }
    actual = tasks._enhance_docker_params(**test_kwargs)

    assert actual == {'envs': {}, 'docker_config': {}, 'ports': [], 'volumes': [], "service_id": None }

    # Good - Test just docker config ports and volumes

    test_kwargs = { "docker_config": { "ports": ["1:1", "2:2"],
        "volumes": [{"container": "somewhere", "host": "somewhere else"}] },
        "service_id": None }
    actual = tasks._enhance_docker_params(**test_kwargs)

    assert actual == {'envs': {}, 'docker_config': {'ports': ['1:1', '2:2'],
        'volumes': [{'host': 'somewhere else', 'container': 'somewhere'}]},
        'ports': ['1:1', '2:2'], 'volumes': [{'host': 'somewhere else',
            'container': 'somewhere'}], "service_id": None}

    # Good - Test just docker config ports and volumes with overrrides

    test_kwargs = { "docker_config": { "ports": ["1:1", "2:2"],
        "volumes": [{"container": "somewhere", "host": "somewhere else"}] },
        "ports": ["3:3", "4:4"], "volumes": [{"container": "nowhere", "host":
        "nowhere else"}],
        "service_id": None }
    actual = tasks._enhance_docker_params(**test_kwargs)

    assert actual == {'envs': {}, 'docker_config': {'ports': ['1:1', '2:2'],
        'volumes': [{'host': 'somewhere else', 'container': 'somewhere'}]},
        'ports': ['1:1', '2:2', '3:3', '4:4'], 'volumes': [{'host': 'somewhere else',
            'container': 'somewhere'}, {'host': 'nowhere else', 'container':
            'nowhere'}], "service_id": None}

    # Good

    test_kwargs = { "docker_config": {}, "service_id": "zed",
            "deployment_id": "abc" }
    actual = tasks._enhance_docker_params(**test_kwargs)

    assert actual["envs"] == {}


def test_notify_container(mockconfig):
    from k8splugin import tasks

    test_input = { "docker_config": { "policy": { "trigger_type": "unknown" } } }
    assert [] == tasks._notify_container(**test_input)
