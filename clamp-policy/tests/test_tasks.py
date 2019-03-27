# ================================================================================
# Copyright (c) 2019 Wipro Limited Intellectual Property. All rights reserved.
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

"""unit tests for tasks in clamppolicyplugin"""

import json

import pytest
from cloudify.exceptions import NonRecoverableError
from cloudify.state import current_ctx

from clamppolicyplugin import tasks
from tests.log_ctx import CtxLogger
from tests.mock_cloudify_ctx import (TARGET_NODE_ID, TARGET_NODE_NAME,
                                     MockCloudifyContextFull)
from tests.mock_setup import (CONFIG_NAME, MONKEYED_POLICY_ID, POLICY_BODY,
                              POLICY_ID, POLICY_MODEL_ID, POLICY_NAME, MonkeyedNode,
                              MonkeyedPolicyBody, MonkeyedResponse)

from cloudify.mocks import MockCloudifyContext
from cloudify.state import current_ctx

def monkeyed_policy_handler_get(full_path, headers=None):
    """monkeypatch for the GET to policy-engine"""
    return MonkeyedResponse(full_path, headers,
        MonkeyedPolicyBody.create_policy(MONKEYED_POLICY_ID))

def test_policy_get():
    """test policy_get operation on clamp.nodes.policy node"""
    mock_ctx = MockCloudifyContext(node_id='policy_model_id',node_name='clamp.nodes.policy')
    current_ctx.set(mock_ctx)
    tasks.policy_get()