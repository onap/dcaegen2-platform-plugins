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

# Lifecycle interface calls for DockerContainer

import json
import uuid

import requests

from cloudify import ctx
from cloudify.decorators import operation
from cloudify.context import NODE_INSTANCE
from cloudify.exceptions import NonRecoverableError

from .discovery import discover_service_url

POLICY_ID = 'policy_id'
POLICY_REQUIRED = 'policy_required'
POLICY_BODY = 'policy_body'
DCAE_POLICY_TYPE = 'dcae.nodes.policy'

class PolicyHandler(object):
    """talk to policy-handler"""
    SERVICE_NAME_POLICY_HANDLER = "policy_handler"
    X_ECOMP_REQUESTID = 'X-ECOMP-RequestID'
    _url = None

    @staticmethod
    def _lazy_init():
        """discover policy-handler"""
        if PolicyHandler._url:
            return

        PolicyHandler._url = "{0}/policy_latest".format(
            discover_service_url(PolicyHandler.SERVICE_NAME_POLICY_HANDLER)
        )

    @staticmethod
    def get_latest_policy(policy_id):
        """retrieve the latest policy for policy_id from policy-handler"""
        PolicyHandler._lazy_init()

        ph_path = "{0}/{1}".format(PolicyHandler._url, policy_id)
        headers = {PolicyHandler.X_ECOMP_REQUESTID: str(uuid.uuid4())}

        ctx.logger.info("getting latest policy from {0} headers={1}".format( \
            ph_path, json.dumps(headers)))
        res = requests.get(ph_path, headers=headers)
        res.raise_for_status()

        if res.status_code == requests.codes.ok:
            return res.json()
        return {}

#########################################################
@operation
def policy_get(**kwargs):
    """retrieve the latest policy_body for policy_id property and save it in runtime_properties"""
    if ctx.type != NODE_INSTANCE or DCAE_POLICY_TYPE not in ctx.node.type_hierarchy:
        error = "can only invoke policy_get on node of type {0}".format(DCAE_POLICY_TYPE)
        ctx.logger.error(error)
        raise NonRecoverableError(error)

    if POLICY_ID not in ctx.node.properties:
        error = "no {0} found in ctx.node.properties".format(POLICY_ID)
        ctx.logger.error(error)
        raise NonRecoverableError(error)

    try:
        policy_id = ctx.node.properties[POLICY_ID]
        policy = PolicyHandler.get_latest_policy(policy_id)
        if not policy:
            raise NonRecoverableError("policy not found for policy_id {0}".format(policy_id))

        ctx.logger.info("found policy {0}".format(json.dumps(policy)))
        if POLICY_BODY in policy:
            ctx.instance.runtime_properties[POLICY_BODY] = policy[POLICY_BODY]

    except Exception as ex:
        error = "failed to get policy: {0}".format(str(ex))
        ctx.logger.error(error)
        if ctx.node.properties.get(POLICY_REQUIRED, True):
            raise NonRecoverableError(error)
