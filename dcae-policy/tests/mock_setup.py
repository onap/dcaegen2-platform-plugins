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

"""unit tests for tasks in dcaepolicyplugin"""

import json
import logging
from datetime import datetime, timedelta

from tests.mock_cloudify_ctx import MockCloudifyContextFull

LOG_FILE = 'logs/test_dcaepolicyplugin.log'
POLICY_ID = 'policy_id'
POLICY_VERSION = "policyVersion"
POLICY_NAME = "policyName"
POLICY_BODY = 'policy_body'
POLICY_CONFIG = 'config'
CONFIG_NAME = "ConfigName"
MONKEYED_POLICY_ID = 'monkeyed.Config_peach'

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
                fmt='%(asctime)s.%(msecs)03d %(levelname)+8s ' +
                    '%(threadName)s %(name)s.%(funcName)s: %(message)s',
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
                "ONAPName": "DCAE",
                CONFIG_NAME: "alex_config_name"
            },
            "responseAttributes": {},
            "property": None
        }

    @staticmethod
    def create_policy(policy_id, policy_version=1):
        """returns the whole policy object for policy_id and policy_version"""
        return {
            POLICY_ID: policy_id,
            POLICY_BODY: MonkeyedPolicyBody.create_policy_body(policy_id, policy_version)
        }

    @staticmethod
    def is_the_same_dict(policy_body_1, policy_body_2):
        """check whether both policy_body objects are the same"""
        if not isinstance(policy_body_1, dict) or not isinstance(policy_body_2, dict):
            return False
        for key in policy_body_1.keys():
            if key not in policy_body_2:
                return False

            val_1 = policy_body_1[key]
            val_2 = policy_body_2[key]
            if isinstance(val_1, dict) \
            and not MonkeyedPolicyBody.is_the_same_dict(val_1, val_2):
                return False
            if (val_1 is None and val_2 is not None) \
            or (val_1 is not None and val_2 is None) \
            or (val_1 != val_2):
                return False
        return True


class MonkeyedResponse(object):
    """Monkey response"""
    def __init__(self, full_path, headers=None, resp_json=None):
        self.full_path = full_path
        self.status_code = 200
        self.headers = headers or {}
        self.resp_json = resp_json
        self.text = json.dumps(resp_json or {})

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
