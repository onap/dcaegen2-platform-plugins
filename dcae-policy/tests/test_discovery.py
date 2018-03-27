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

"""unit tests for discovery in dcaepolicyplugin"""

import base64
import json

import pytest
from cloudify.state import current_ctx

from dcaepolicyplugin import discovery, tasks
from tests.log_ctx import CtxLogger
from tests.mock_cloudify_ctx import MockCloudifyContextFull
from tests.mock_setup import (MONKEYED_POLICY_ID, POLICY_ID, MonkeyedNode,
                              MonkeyedResponse)

POLICY_HANDLER_FROM_KV = "http:policy_handler_from_kv:25577"


def monkeyed_discovery_get_failure(full_path):
    """monkeypatch for the GET to consul"""
    return MonkeyedResponse(full_path)


def test_discovery_failure(monkeypatch):
    """test finding policy-handler in consul"""
    monkeypatch.setattr('requests.get', monkeyed_discovery_get_failure)

    node_policy = MonkeyedNode(
        'test_dcae_policy_node_id',
        'test_dcae_policy_node_name',
        tasks.DCAE_POLICY_TYPE,
        {POLICY_ID: MONKEYED_POLICY_ID}
    )
    try:
        current_ctx.set(node_policy.ctx)
        tasks.PolicyHandler._lazy_init()
        assert tasks.PolicyHandler.DEFAULT_URL == tasks.PolicyHandler._url

    finally:
        tasks.PolicyHandler._url = None
        MockCloudifyContextFull.clear()
        current_ctx.clear()


def monkeyed_discovery_get_kv(full_path):
    """monkeypatch for the GET to consul"""
    if full_path.startswith(discovery.CONSUL_SERVICE_URL.format("")):
        return MonkeyedResponse(full_path)

    if full_path.startswith(discovery.CONSUL_KV_MASK.format("")):
        value = base64.b64encode(json.dumps(
            {tasks.DCAE_POLICY_PLUGIN: {
                tasks.PolicyHandler.SERVICE_NAME_POLICY_HANDLER: {
                    "url": POLICY_HANDLER_FROM_KV}}}
        ))
        return MonkeyedResponse(full_path, {}, [{"Value": value}])

    return MonkeyedResponse(full_path)


def test_discovery_kv(monkeypatch):
    """test finding policy-handler in consul"""
    monkeypatch.setattr('requests.get', monkeyed_discovery_get_kv)

    node_policy = MonkeyedNode(
        'test_dcae_policy_node_id',
        'test_dcae_policy_node_name',
        tasks.DCAE_POLICY_TYPE,
        {POLICY_ID: MONKEYED_POLICY_ID}
    )
    try:
        current_ctx.set(node_policy.ctx)
        tasks.PolicyHandler._lazy_init()
        assert POLICY_HANDLER_FROM_KV == tasks.PolicyHandler._url

    finally:
        tasks.PolicyHandler._url = None
        MockCloudifyContextFull.clear()
        current_ctx.clear()


def monkeyed_discovery_get(full_path):
    """monkeypatch for the GET to consul"""
    return MonkeyedResponse(full_path, {},
        [{"ServiceAddress": "monkey-policy-handler-address", "ServicePort": "9999"}])


def test_discovery(monkeypatch):
    """test finding policy-handler in consul"""
    monkeypatch.setattr('requests.get', monkeyed_discovery_get)

    node_policy = MonkeyedNode(
        'test_dcae_policy_node_id',
        'test_dcae_policy_node_name',
        tasks.DCAE_POLICY_TYPE,
        {POLICY_ID: MONKEYED_POLICY_ID}
    )

    try:
        current_ctx.set(node_policy.ctx)
        expected = "http://monkey-policy-handler-address:9999"
        CtxLogger.log_ctx_info("before PolicyHandler._lazy_init")
        tasks.PolicyHandler._lazy_init()
        CtxLogger.log_ctx_info("after PolicyHandler._lazy_init")
        assert expected == tasks.PolicyHandler._url

    finally:
        tasks.PolicyHandler._url = None
        MockCloudifyContextFull.clear()
        current_ctx.clear()
