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


import test_consulif
from dmaapcontrollerif.dmaap_requests import DMaaPControllerHandle

import logging
logger = logging.getLogger("test_mr_lifecycle")

_goodosv2 = {
  'auth_url': 'https://example.com/identity/v2.0',
  'password': 'pw',
  'region': 'r',
  'tenant_name': 'tn',
  'username': 'un'
}


def test_dmaapc (monkeypatch, mockconsul, mockdmaapbc):
    from dmaapplugin.dmaaputils import random_string

    config = mockconsul().get_config('mockkey')['dmaap']
    DMAAP_API_URL = config['url']
    DMAAP_USER = config['username']
    DMAAP_PASS = config['password']
    DMAAP_OWNER = config['owner']

    properties = {'fqdn': 'a.x.example.com', 'openstack': _goodosv2 }
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

    # Make sure there's a topic_name
    if "topic_name" in ctx.node.properties:
        topic_name = ctx.node.properties["topic_name"]
        if topic_name == '' or topic_name.isspace():
            topic_name = random_string(12)
    else:
        topic_name = random_string(12)

    # Make sure there's a topic description
    if "topic_description" in ctx.node.properties:
        topic_description = ctx.node.properties["topic_description"]
    else:
        topic_description = "No description provided"

    # ..and the truly optional setting
    if "txenable" in ctx.node.properties:
        txenable = ctx.node.properties["txenable"]
    else:
        txenable= False

    if "replication_case" in ctx.node.properties:
        replication_case = ctx.node.properties["replication_case"]
    else:
        replication_case = None

    if "global_mr_url" in ctx.node.properties:
        global_mr_url = ctx.node.properties["global_mr_url"]
    else:
        global_mr_url = None

    dmc = DMaaPControllerHandle(DMAAP_API_URL, DMAAP_USER, DMAAP_PASS, ctx.logger)
    ctx.logger.info("Attempting to create topic name {0}".format(topic_name))
    t = dmc.create_topic(topic_name, topic_description, txenable, DMAAP_OWNER, replication_case, global_mr_url)

    # Capture important properties from the result
    topic = t.json()
    ctx.instance.runtime_properties["fqtn"] = topic["fqtn"]

    # test DMaaPControllerHandle functions
    path = "myPath"
    url = dmc._make_url(path)
    rc = dmc._get_resource(path)
    rc = dmc._create_resource(path, None)
    rc = dmc._delete_resource(path)
