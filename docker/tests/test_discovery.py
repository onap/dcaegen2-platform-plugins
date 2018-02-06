# ============LICENSE_START=======================================================
# org.onap.dcae
# ================================================================================
# Copyright (c) 2017-2018 AT&T Intellectual Property. All rights reserved.
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

import pytest
from functools import partial
import requests
from dockerplugin import discovery as dis


def test_wrap_consul_call():
    def foo(a, b, c="default"):
        return " ".join([a, b, c])

    wrapped_foo = partial(dis._wrap_consul_call, foo)
    assert wrapped_foo("hello", "world") == "hello world default"
    assert wrapped_foo("hello", "world", c="new masters") == "hello world new masters"

    def foo_connection_error(a, b, c):
        raise requests.exceptions.ConnectionError("simulate failed connection")

    wrapped_foo = partial(dis._wrap_consul_call, foo_connection_error)
    with pytest.raises(dis.DiscoveryConnectionError):
        wrapped_foo("a", "b", "c")


def test_generate_service_component_name():
    component_type = "some-component-type"
    name = dis.generate_service_component_name(component_type)
    assert name.split("_")[1] == component_type


def test_find_matching_services():
    services = { "component_dockerhost_1": ["foo", "bar"],
            "platform_dockerhost": [], "component_dockerhost_2": ["baz"] }
    assert sorted(["component_dockerhost_1", "component_dockerhost_2"]) \
        == sorted(dis._find_matching_services(services, "component_dockerhost", []))

    assert ["component_dockerhost_1"] == dis._find_matching_services(services, \
            "component_dockerhost", ["foo", "bar"])

    assert ["component_dockerhost_1"] == dis._find_matching_services(services, \
            "component_dockerhost", ["foo"])

    assert [] == dis._find_matching_services(services, "unknown", ["foo"])


def test_is_healthy_pure():
    def fake_is_healthy(name):
        return 0, [{ "Checks": [{"Status": "passing"}] }]

    assert True == dis._is_healthy_pure(fake_is_healthy, "some-component")

