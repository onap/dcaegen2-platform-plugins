# ============LICENSE_START=======================================================
# org.onap.dcae
# ================================================================================
# Copyright (c) 2017-2018 AT&T Intellectual Property. All rights reserved.
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
#
# ECOMP is a trademark and service mark of AT&T Intellectual Property.

import pytest
import requests
from cloudify.mocks import MockCloudifyContext
from cloudify.state import current_ctx
from cloudify import ctx
from cloudify.decorators import operation
from cloudify.exceptions import NonRecoverableError
from cloudify.exceptions import RecoverableError

_goodosv2 = {
  'auth_url': 'https://example.com/identity/v2.0',
  'password': 'pw',
  'region': 'r',
  'tenant_name': 'tn',
  'username': 'un'
}


def test_create_topic(monkeypatch, mockconsul, mockdmaapbc):
    import dmaapplugin
    from dmaapplugin import mr_lifecycle
    properties = {'fqdn': 'a.x.example.com', 'openstack': _goodosv2, 'fqtn': 'test_fqtn' }
    mock_ctx = MockCloudifyContext(
        node_id='test_node_id',
        node_name='test_node_name',
        properties=properties,
        runtime_properties = {
           "admin": { "user": "admin_user" },
           "user": { "user": "user_user" },
           "viewer": { "user": "viewer_user" }
        })

    current_ctx.set(mock_ctx)

    kwargs = { "topic_name": "ONAP_test",
            "topic_description": "onap dmaap plugin unit test topic"}

    mr_lifecycle.create_topic(**kwargs)
    mr_lifecycle.get_existing_topic(**kwargs)
    mr_lifecycle.delete_topic(**kwargs)
