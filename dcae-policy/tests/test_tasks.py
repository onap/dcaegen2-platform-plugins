# ================================================================================
# Copyright (c) 2017-2020 AT&T Intellectual Property. All rights reserved.
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

"""unit tests for tasks in dcaepolicyplugin"""

import json

import pytest
from cloudify.exceptions import NonRecoverableError
from cloudify.state import current_ctx

from dcaepolicyplugin import tasks
from tests.log_ctx import CtxLogger
from tests.mock_cloudify_ctx import (TARGET_NODE_ID, TARGET_NODE_NAME,
                                     MockCloudifyContextFull)
from tests.mock_setup import (CONFIG_NAME, MONKEYED_POLICY_ID, POLICY_BODY,
                              POLICY_ID, POLICY_NAME, MonkeyedNode,
                              MonkeyedPolicyBody, MonkeyedResponse)


LATEST_POLICIES = "latest_policies"


def monkeyed_policy_handler_get(full_path, headers=None, **kwargs):
    """monkeypatch for the GET to policy-engine"""
    return MonkeyedResponse(full_path, headers,
        MonkeyedPolicyBody.create_policy(MONKEYED_POLICY_ID))


def test_policy_get(monkeypatch):
    """test policy_get operation on dcae.nodes.policy node"""
    tasks.PolicyHandler._url = tasks.PolicyHandler.DEFAULT_URL
    monkeypatch.setattr('requests.get', monkeyed_policy_handler_get)

    node_policy = MonkeyedNode(
        'test_dcae_policy_node_id',
        'test_dcae_policy_node_name',
        tasks.DCAE_POLICY_TYPE,
        {POLICY_ID: MONKEYED_POLICY_ID}
    )

    try:
        current_ctx.set(node_policy.ctx)
        CtxLogger.log_ctx_info("before policy_get")
        tasks.policy_get()
        CtxLogger.log_ctx_info("after policy_get")

        expected = {
            POLICY_BODY: MonkeyedPolicyBody.create_policy_body(MONKEYED_POLICY_ID)
        }
        result = node_policy.ctx.instance.runtime_properties
        node_policy.ctx.logger.info("expected runtime_properties: {0}".format(
            json.dumps(expected)))
        node_policy.ctx.logger.info("runtime_properties: {0}".format(json.dumps(result)))
        assert MonkeyedPolicyBody.is_the_same_dict(result, expected)
        assert MonkeyedPolicyBody.is_the_same_dict(expected, result)

    finally:
        MockCloudifyContextFull.clear()
        current_ctx.clear()


def test_policy_get_fail(monkeypatch):
    """test policy_get operation on non dcae.nodes.policy node"""
    tasks.PolicyHandler._url = tasks.PolicyHandler.DEFAULT_URL
    monkeypatch.setattr('requests.get', monkeyed_policy_handler_get)

    node_policy = MonkeyedNode(
        'test_dcae_policy_node_id',
        'test_dcae_policy_node_name',
        tasks.DCAE_POLICY_TYPE,
        {POLICY_ID: MONKEYED_POLICY_ID}
    )

    node_ms = MonkeyedNode(
        'test_ms_id', 'test_ms_name', "ms.nodes.type", None,
        [{TARGET_NODE_ID: node_policy.node_id, TARGET_NODE_NAME: node_policy.node_name}]
    )

    try:
        current_ctx.set(node_ms.ctx)
        CtxLogger.log_ctx_info("ctx of node_ms not policy type")
        with pytest.raises(NonRecoverableError) as excinfo:
            tasks.policy_get()
        CtxLogger.log_ctx_info("node_ms not policy type boom: {0}".format(str(excinfo.value)))
        assert "unexpected node type " in str(excinfo.value)

    finally:
        MockCloudifyContextFull.clear()
        current_ctx.clear()


def monkeyed_policy_handler_find(full_path, json, headers, **kwargs):
    """monkeypatch for the GET to policy-engine"""
    return MonkeyedResponse(
        full_path, headers,
        {LATEST_POLICIES: {
            MONKEYED_POLICY_ID: MonkeyedPolicyBody.create_policy(MONKEYED_POLICY_ID)}}
    )


def test_policies_find(monkeypatch):
    """test policy_get operation on dcae.nodes.policies node"""
    tasks.PolicyHandler._url = tasks.PolicyHandler.DEFAULT_URL
    monkeypatch.setattr('requests.post', monkeyed_policy_handler_find)

    node_policies = MonkeyedNode(
        'test_dcae_policies_node_id',
        'test_dcae_policies_node_name',
        tasks.DCAE_POLICIES_TYPE,
        {
            tasks.POLICY_FILTER: {
                POLICY_NAME: MONKEYED_POLICY_ID,
                tasks.CONFIG_ATTRIBUTES: json.dumps({
                    CONFIG_NAME: "alex_config_name"
                })
            }
        }
    )

    try:
        current_ctx.set(node_policies.ctx)
        CtxLogger.log_ctx_info("before policy_get")
        tasks.policy_get()
        CtxLogger.log_ctx_info("after policy_get")

        expected = {
            tasks.POLICIES_FILTERED: {
                MONKEYED_POLICY_ID: MonkeyedPolicyBody.create_policy(MONKEYED_POLICY_ID)}}

        result = node_policies.ctx.instance.runtime_properties
        node_policies.ctx.logger.info("expected runtime_properties: {0}".format(
            json.dumps(expected)))
        node_policies.ctx.logger.info("runtime_properties: {0}".format(json.dumps(result)))
        assert MonkeyedPolicyBody.is_the_same_dict(result, expected)
        assert MonkeyedPolicyBody.is_the_same_dict(expected, result)

    finally:
        MockCloudifyContextFull.clear()
        current_ctx.clear()


def test_policies_find_fail(monkeypatch):
    """test policy_get operation on non dcae.nodes.policies node"""
    tasks.PolicyHandler._url = tasks.PolicyHandler.DEFAULT_URL
    monkeypatch.setattr('requests.post', monkeyed_policy_handler_find)

    node_policies = MonkeyedNode(
        'test_dcae_policies_node_id',
        'test_dcae_policies_node_name',
        tasks.DCAE_POLICIES_TYPE,
        {
            tasks.POLICY_FILTER: {
                POLICY_NAME: MONKEYED_POLICY_ID,
                tasks.CONFIG_ATTRIBUTES: json.dumps({
                    CONFIG_NAME: "alex_config_name"
                })
            }
        }
    )
    node_ms_multi = MonkeyedNode(
        'test_ms_multi_id', 'test_ms_multi_name', "ms.nodes.type",
        None,
        [{TARGET_NODE_ID: node_policies.node_id, TARGET_NODE_NAME: node_policies.node_name}]
    )

    try:
        current_ctx.set(node_ms_multi.ctx)
        CtxLogger.log_ctx_info("ctx of node_ms_multi not policy type")
        with pytest.raises(NonRecoverableError) as excinfo:
            tasks.policy_get()
        CtxLogger.log_ctx_info("node_ms_multi not policy type boom: {0}".format(str(excinfo.value)))
        assert "unexpected node type " in str(excinfo.value)

    finally:
        MockCloudifyContextFull.clear()
        current_ctx.clear()
