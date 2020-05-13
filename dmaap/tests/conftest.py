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

import pytest

import requests

@pytest.fixture()
def mockconsul(monkeypatch):
    """ Override the regular Consul interface"""
    def fake_get_config(self, key):
        config={'dmaap': {
            'username': 'testuser@dmaaptest.example.com',
            'url': 'https://dmaaptest.example.com:8443/webapi',
            'password' : 'testpassword',
            'owner': 'dcaeorch'
        }}
        return config

    def fake_get_service(self, service_name):
        service_address = "myAddress"
        service_port= "8443"
        return service_address, service_port

    def fake_add_to_entry(self, key, add_name, add_value):
        return True

    def fake_delete_entry(self, entry_name):
        return True

    def fake_init(self, api_url, user, password, logger):
        pass

    from consulif.consulif import ConsulHandle
    monkeypatch.setattr(ConsulHandle, 'get_config', fake_get_config)
    monkeypatch.setattr(ConsulHandle, 'get_service', fake_get_service)
    monkeypatch.setattr(ConsulHandle, 'add_to_entry', fake_add_to_entry)
    monkeypatch.setattr(ConsulHandle, 'delete_entry', fake_delete_entry)
    monkeypatch.setattr(ConsulHandle, '__init__', fake_init)

    def get_handle():
        return ConsulHandle('mockconsul', None, None, None)
    return get_handle


@pytest.fixture()
def mockdmaapbc(monkeypatch):

    def fake_get(url, auth):
    #    print "fake_get: {0}, {1}".format(url, auth)
        r = requests.Response()
        r.status_code = 200
        return r
    def fake_post(url, auth, json):
    #    print "fake_post: {0}, {1}, {2}".format(url, auth, json)
        r = requests.Response()
        r.status_code = 200
        return r
    def fake_delete(url, auth):
    #    print "fake_delete: {0}, {1}".format(url, auth)
        r = requests.Response()
        r.status_code = 200
        return r
    def fake_json(self):
        return {"fqtn":"test_fqtn"}

    import requests
    monkeypatch.setattr(requests.Response, "json", fake_json)
    monkeypatch.setattr(requests, "get", fake_get)
    monkeypatch.setattr(requests, "post", fake_post)
    monkeypatch.setattr(requests, "delete", fake_delete)

