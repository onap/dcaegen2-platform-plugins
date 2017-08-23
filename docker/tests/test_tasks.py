# ============LICENSE_START=======================================================
# org.onap.dcae
# ================================================================================
# Copyright (c) 2017 AT&T Intellectual Property. All rights reserved.
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
from cloudify.exceptions import NonRecoverableError
import dockerplugin
from dockerplugin import tasks


def test_parse_streams(monkeypatch):
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
    test_input = { "streams_publishes": {},
            "streams_subscribes": [{"name": "topic01", "type": "message_router"},
                {"name": "feed01", "type": "data_router", "username": "hero",
                    "password": "123456"}] }

    expected = {'feed01': {'type': 'data_router', 'name': 'feed01',
                    'username': 'hero', 'password': '123456'},
            'streams_publishes': {},
            'streams_subscribes': [{'type': 'message_router', 'name': 'topic01'},
                {'type': 'data_router', 'name': 'feed01', 'username': 'hero',
                    'password': '123456'}],
            'topic01': {'type': 'message_router', 'name': 'topic01'}}

    assert expected == tasks._parse_streams(**test_input)

    # Good case for streams_subscribes (password generated)
    test_input = { "streams_publishes": {},
            "streams_subscribes": [{"name": "topic01", "type": "message_router"},
                {"name": "feed01", "type": "data_router", "username": None,
                    "password": None}] }

    def not_so_random(n):
        return "nosurprise"

    monkeypatch.setattr(dockerplugin.utils, "random_string", not_so_random)

    expected = {'feed01': {'type': 'data_router', 'name': 'feed01',
                    'username': 'nosurprise', 'password': 'nosurprise'},
            'streams_publishes': {},
            'streams_subscribes': [{'type': 'message_router', 'name': 'topic01'},
                {'type': 'data_router', 'name': 'feed01', 'username': None,
                    'password': None}],
            'topic01': {'type': 'message_router', 'name': 'topic01'}}

    assert expected == tasks._parse_streams(**test_input)


def test_setup_for_discovery_streams(monkeypatch):
    test_input = {'feed01': {'type': 'data_router', 'name': 'feed01',
                'username': 'hero', 'password': '123456', 'location': 'Bedminster'},
            'streams_publishes': {},
            'streams_subscribes': [{'type': 'message_router', 'name': 'topic01'},
                {'type': 'data_router', 'name': 'feed01', 'username': 'hero',
                    'password': '123456', 'location': 'Bedminster'}],
            'topic01': {'type': 'message_router', 'name': 'topic01'}}
    test_input["name"] = "some-foo-service-component"

    # Good case
    def fake_add_to_entry(conn, key, add_name, add_value):
        """
        This fake method will check all the pieces that are used to make store
        details in Consul
        """
        if key != test_input["name"] + ":dmaap":
            return None
        if add_name != "feed01":
            return None
        if add_value != {"location": "Bedminster", "delivery_url": None,
                "username": "hero", "password": "123456", "subscriber_id": None}:
            return None

        return "SUCCESS!"

    monkeypatch.setattr(dockerplugin.discovery, "add_to_entry",
            fake_add_to_entry)

    assert tasks._setup_for_discovery_streams(**test_input) == test_input

    # Good case - no data router subscribers
    test_input = {"streams_publishes": [{"name": "topic00", "type": "message_router"}],
            'streams_subscribes': [{'type': 'message_router', 'name': 'topic01'}]}
    test_input["name"] = "some-foo-service-component"

    assert tasks._setup_for_discovery_streams(**test_input) == test_input

    # Bad case - something happened from the Consul call
    test_input = {'feed01': {'type': 'data_router', 'name': 'feed01',
                'username': 'hero', 'password': '123456', 'location': 'Bedminster'},
            'streams_publishes': {},
            'streams_subscribes': [{'type': 'message_router', 'name': 'topic01'},
                {'type': 'data_router', 'name': 'feed01', 'username': 'hero',
                    'password': '123456', 'location': 'Bedminster'}],
            'topic01': {'type': 'message_router', 'name': 'topic01'}}
    test_input["name"] = "some-foo-service-component"

    def barf(conn, key, add_name, add_value):
        raise RuntimeError("Barf")

    monkeypatch.setattr(dockerplugin.discovery, "add_to_entry",
            barf)

    with pytest.raises(NonRecoverableError):
        tasks._setup_for_discovery_streams(**test_input)


def test_update_delivery_url(monkeypatch):
    test_input = {'feed01': {'type': 'data_router', 'name': 'feed01',
                'username': 'hero', 'password': '123456', 'location': 'Bedminster',
                'route': 'some-path'},
            'streams_publishes': {},
            'streams_subscribes': [{'type': 'message_router', 'name': 'topic01'},
                {'type': 'data_router', 'name': 'feed01', 'username': 'hero',
                    'password': '123456', 'location': 'Bedminster',
                    'route': 'some-path'}],
            'topic01': {'type': 'message_router', 'name': 'topic01'}}
    test_input["service_component_name"] = "some-foo-service-component"

    def fake_lookup_service(name, with_port=False):
        if with_port:
            return "10.100.1.100:8080"
        else:
            return

    monkeypatch.setattr(dockerplugin.tasks, "_lookup_service",
            fake_lookup_service)

    expected = copy.deepcopy(test_input)
    expected["feed01"]["delivery_url"] = "http://10.100.1.100:8080/some-path"

    assert tasks._update_delivery_url(**test_input) == expected


def test_enhance_docker_params():
    # Good - Test empty docker config

    test_kwargs = { "docker_config": {} }
    actual = tasks._enhance_docker_params(**test_kwargs)

    assert actual == {'envs': {}, 'docker_config': {}}

    # Good - Test just docker config ports and volumes

    test_kwargs = { "docker_config": { "ports": ["1:1", "2:2"],
        "volumes": [{"container": "somewhere", "host": "somewhere else"}] } }
    actual = tasks._enhance_docker_params(**test_kwargs)

    assert actual == {'envs': {}, 'docker_config': {'ports': ['1:1', '2:2'],
        'volumes': [{'host': 'somewhere else', 'container': 'somewhere'}]},
        'ports': ['1:1', '2:2'], 'volumes': [{'host': 'somewhere else',
            'container': 'somewhere'}]}

    # Good - Test just docker config ports and volumes with overrrides

    test_kwargs = { "docker_config": { "ports": ["1:1", "2:2"],
        "volumes": [{"container": "somewhere", "host": "somewhere else"}] },
        "ports": ["3:3", "4:4"], "volumes": [{"container": "nowhere", "host":
        "nowhere else"}]}
    actual = tasks._enhance_docker_params(**test_kwargs)

    assert actual == {'envs': {}, 'docker_config': {'ports': ['1:1', '2:2'],
        'volumes': [{'host': 'somewhere else', 'container': 'somewhere'}]},
        'ports': ['1:1', '2:2', '3:3', '4:4'], 'volumes': [{'host': 'somewhere else', 
            'container': 'somewhere'}, {'host': 'nowhere else', 'container':
            'nowhere'}]}

