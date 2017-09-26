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

import json
import logging
from datetime import datetime, timedelta

import pytest

from cloudify.state import current_ctx
from cloudify.exceptions import NonRecoverableError

from mock_cloudify_ctx import MockCloudifyContextFull, TARGET_NODE_ID, TARGET_NODE_NAME
from log_ctx import CtxLogger

from dcaepolicyplugin import tasks

DCAE_POLICY_TYPE = 'dcae.nodes.policy'
POLICY_ID = 'policy_id'
POLICY_VERSION = "policyVersion"
POLICY_NAME = "policyName"
POLICY_BODY = 'policy_body'
POLICY_CONFIG = 'config'
MONKEYED_POLICY_ID = 'monkeyed.Config_peach'
LOG_FILE = 'test_dcaepolicyplugin.log'

RUN_TS = datetime.utcnow()

class MonkeyedLogHandler(object):
    """keep the shared logger handler here"""
    _log_handler = None

    @staticmethod
    def add_handler_to(logger):
        """adds the local handler to the logger"""
        if not MonkeyedLogHandler._log_handler:
            MonkeyedLogHandler._log_handler = logging.FileHandler(LOG_FILE)
            MonkeyedLogHandler._log_handler.setLevel(logging.DEBUG)
            formatter = logging.Formatter(
                fmt='%(asctime)s.%(msecs)03d %(levelname)+8s ' + \
                    '%(threadName)s %(name)s.%(funcName)s: %(message)s', \
                datefmt='%Y%m%d_%H%M%S')
            MonkeyedLogHandler._log_handler.setFormatter(formatter)
        logger.addHandler(MonkeyedLogHandler._log_handler)

class MonkeyedPolicyBody(object):
    """policy body that policy-engine returns"""
    @staticmethod
    def create_policy_body(policy_id, policy_version=1):
        """returns a fake policy-body"""
        prev_ver = policy_version - 1
        timestamp = RUN_TS + timedelta(hours=prev_ver)

        prev_ver = str(prev_ver)
        this_ver = str(policy_version)
        config = {
            "policy_updated_from_ver": prev_ver,
            "policy_updated_to_ver": this_ver,
            "policy_hello": "world!",
            "policy_updated_ts": timestamp.isoformat()[:-3] + 'Z',
            "updated_policy_id": policy_id
        }
        return {
            "policyConfigMessage": "Config Retrieved! ",
            "policyConfigStatus": "CONFIG_RETRIEVED",
            "type": "JSON",
            POLICY_NAME: "{0}.{1}.xml".format(policy_id, this_ver),
            POLICY_VERSION: this_ver,
            POLICY_CONFIG: config,
            "matchingConditions": {
                "ECOMPName": "DCAE",
                "ConfigName": "alex_config_name"
            },
            "responseAttributes": {},
            "property": None
        }

    @staticmethod
    def create_policy(policy_id, policy_version=1):
        """returns the whole policy object for policy_id and policy_version"""
        return {
            POLICY_ID : policy_id,
            POLICY_BODY : MonkeyedPolicyBody.create_policy_body(policy_id, policy_version)
        }

    @staticmethod
    def is_the_same_dict(policy_body_1, policy_body_2):
        """check whether both policy_body objects are the same"""
        if not isinstance(policy_body_1, dict) or not isinstance(policy_body_2, dict):
            return False
        for key in policy_body_1.keys():
            if key not in policy_body_2:
                return False
            if isinstance(policy_body_1[key], dict):
                return MonkeyedPolicyBody.is_the_same_dict(
                    policy_body_1[key], policy_body_2[key])
            if (policy_body_1[key] is None and policy_body_2[key] is not None) \
            or (policy_body_1[key] is not None and policy_body_2[key] is None) \
            or (policy_body_1[key] != policy_body_2[key]):
                return False
        return True

class MonkeyedResponse(object):
    """Monkey response"""
    def __init__(self, full_path, headers=None, resp_json=None):
        self.full_path = full_path
        self.status_code = 200
        self.headers = headers
        self.resp_json = resp_json

    def json(self):
        """returns json of response"""
        return self.resp_json

    def raise_for_status(self):
        """always happy"""
        pass

class MonkeyedNode(object):
    """node in cloudify"""
    BLUEPRINT_ID = 'test_dcae_policy_bp_id'
    DEPLOYMENT_ID = 'test_dcae_policy_dpl_id'
    EXECUTION_ID = 'test_dcae_policy_exe_id'

    def __init__(self, node_id, node_name, node_type, properties, relationships=None):
        self.node_id = node_id
        self.node_name = node_name
        self.ctx = MockCloudifyContextFull(
            node_id=self.node_id,
            node_name=self.node_name,
            node_type=node_type,
            blueprint_id=MonkeyedNode.BLUEPRINT_ID,
            deployment_id=MonkeyedNode.DEPLOYMENT_ID,
            execution_id=MonkeyedNode.EXECUTION_ID,
            properties=properties,
            relationships=relationships
        )
        MonkeyedLogHandler.add_handler_to(self.ctx.logger)

def monkeyed_discovery_get(full_path):
    """monkeypatch for the GET to consul"""
    return MonkeyedResponse(full_path, {}, \
        [{"ServiceAddress":"monkey-policy-handler-address", "ServicePort": "9999"}])

def monkeyed_policy_handler_get(full_path, headers):
    """monkeypatch for the GET to policy-engine"""
    return MonkeyedResponse(full_path, headers, \
        MonkeyedPolicyBody.create_policy(MONKEYED_POLICY_ID))

def test_discovery(monkeypatch):
    """test finding policy-handler in consul"""
    monkeypatch.setattr('requests.get', monkeyed_discovery_get)
    expected = "http://monkey-policy-handler-address:9999/policy_latest"
    tasks.PolicyHandler._lazy_init()
    assert expected == tasks.PolicyHandler._url

def test_policy_get(monkeypatch):
    """test policy_get operation on dcae.nodes.policy node"""
    monkeypatch.setattr('requests.get', monkeyed_policy_handler_get)

    node_policy = MonkeyedNode(
        'test_dcae_policy_node_id',
        'test_dcae_policy_node_name',
        DCAE_POLICY_TYPE,
        {POLICY_ID: MONKEYED_POLICY_ID}
    )

    try:
        current_ctx.set(node_policy.ctx)
        CtxLogger.log_ctx_info("before policy_get")
        tasks.policy_get()
        CtxLogger.log_ctx_info("after policy_get")

        expected = {
            POLICY_BODY : MonkeyedPolicyBody.create_policy_body(MONKEYED_POLICY_ID)
        }
        result = node_policy.ctx.instance.runtime_properties
        node_policy.ctx.logger.info("expected runtime_properties: {0}".format(
            json.dumps(expected)))
        node_policy.ctx.logger.info("runtime_properties: {0}".format(json.dumps(result)))
        assert MonkeyedPolicyBody.is_the_same_dict(result, expected)
        assert MonkeyedPolicyBody.is_the_same_dict(expected, result)

        node_ms = MonkeyedNode('test_ms_id', 'test_ms_name', "ms.nodes.type", None, \
            [{TARGET_NODE_ID: node_policy.node_id,
              TARGET_NODE_NAME: node_policy.node_name}])
        current_ctx.set(node_ms.ctx)
        CtxLogger.log_ctx_info("ctx of node_ms not policy type")
        with pytest.raises(NonRecoverableError) as excinfo:
            tasks.policy_get()
        CtxLogger.log_ctx_info("node_ms not policy type boom: {0}".format(str(excinfo.value)))
        assert "can only invoke policy_get on node of type dcae.nodes.policy" in str(excinfo.value)

    finally:
        MockCloudifyContextFull.clear()
        current_ctx.clear()
