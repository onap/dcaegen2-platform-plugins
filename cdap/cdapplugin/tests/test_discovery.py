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

from cdapcloudify import get_module_logger
from cdapcloudify  import discovery
import pytest
import requests
import collections
import json

logger = get_module_logger(__name__)

_TEST_BROKER_NAME = "test_broker"
_TEST_SCN = "test_scn"


class FakeResponse:
    def __init__(self, status_code, text, json = {}):
        self.status_code = status_code
        self.json = json #this is kind of misleading as the broker doesnt return the input as output but this cheat makes testing easier
        self.text = text

def _fake_putpost(url, json, headers):
    return FakeResponse(status_code = 200,
                        json = json,
                        text = "URL: {0}, headers {1}".format(url, headers))

def _fake_delete(url):
    return FakeResponse(status_code = 200, text = "URL: {0}".format(url))

def _fake_get_broker_url(cdap_broker_name, service_component_name, logger):
    return "http://{ip}:{port}/application/{appname}".format(ip="666.666.666.666", port="666", appname=service_component_name)

def test_put_broker(monkeypatch):
    monkeypatch.setattr('requests.put', _fake_putpost)
    monkeypatch.setattr('cdapcloudify.discovery._get_broker_url', _fake_get_broker_url)
    R = discovery.put_broker(
            _TEST_BROKER_NAME,
            _TEST_SCN,
            "test_ns",
            "test_sn",
            "test_ju",
            "test_an",
            "test_av",
            "test_ac",
            "test_ap",
            "test_se",
            "test_p",
            "test_pp",
            logger)

    assert R.text == "URL: http://666.666.666.666:666/application/test_scn, headers {'content-type': 'application/json'}"
    assert R.json == {'app_preferences': 'test_ap', 'services': 'test_se', 'namespace': 'test_ns', 'programs': 'test_p', 'cdap_application_type': 'program-flowlet', 'app_config': 'test_ac', 'streamname': 'test_sn', 'program_preferences': 'test_pp', 'artifact_name': 'test_an', 'jar_url': 'test_ju', 'artifact_version': 'test_av'}
    assert R.status_code == 200

def test_reconfigure_in_broker(monkeypatch):
    monkeypatch.setattr('requests.put', _fake_putpost)
    monkeypatch.setattr('cdapcloudify.discovery._get_broker_url', _fake_get_broker_url)
    R = discovery.reconfigure_in_broker(
            _TEST_BROKER_NAME,
            _TEST_SCN,
            {"redome" : "baby"},
            "program-flowlet-app-config",
            logger)
    assert R.text == "URL: http://666.666.666.666:666/application/test_scn/reconfigure, headers {'content-type': 'application/json'}"
    assert R.json == {'reconfiguration_type': 'program-flowlet-app-config', 'config': {'redome': 'baby'}}
    assert R.status_code == 200

def test_delete_on_broker(monkeypatch):
    monkeypatch.setattr('requests.delete', _fake_delete)
    monkeypatch.setattr('cdapcloudify.discovery._get_broker_url', _fake_get_broker_url)
    R = discovery.delete_on_broker(
            _TEST_BROKER_NAME,
            _TEST_SCN,
            logger)
    print(R.text)
    assert R.text == "URL: http://666.666.666.666:666/application/test_scn"
    assert R.status_code == 200

def test_multi_delete(monkeypatch):
    pretend_appnames = ['yo1', 'yo2']

    def fake_get(url):
        #return a fake list of app names
        return FakeResponse(status_code = 200,
                            text = json.dumps(pretend_appnames))
    def fake_get_connection_info_from_consul(broker_name, logger):
        return "666.666.666.666", "666"

    monkeypatch.setattr('requests.get', fake_get)
    monkeypatch.setattr('cdapcloudify.discovery._get_connection_info_from_consul', fake_get_connection_info_from_consul)
    monkeypatch.setattr('requests.post', _fake_putpost)
    R = discovery.delete_all_registered_apps(
            _TEST_BROKER_NAME,
            logger)

    assert R.text == "URL: http://666.666.666.666:666/application/delete, headers {'content-type': 'application/json'}"
    assert R.status_code == 200
    assert R.json == {'appnames': pretend_appnames}
