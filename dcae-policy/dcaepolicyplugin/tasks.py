# ================================================================================
# Copyright (c) 2017-2019 AT&T Intellectual Property. All rights reserved.
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

"""tasks are the cloudify operations invoked on interfaces defined in the blueprint"""

import copy
import json
import traceback
import uuid

import requests
from cloudify import ctx
from cloudify.context import NODE_INSTANCE
from cloudify.decorators import operation
from cloudify.exceptions import NonRecoverableError

from .discovery import discover_service_url, discover_value

DCAE_POLICY_PLUGIN = "dcaepolicyplugin"
POLICY_ID = 'policy_id'
POLICY_REQUIRED = 'policy_required'
POLICY_BODY = 'policy_body'
POLICIES_FILTERED = 'policies_filtered'
POLICY_FILTER = 'policy_filter'
LATEST_POLICIES = "latest_policies"

REQUEST_ID = "requestID"

DCAE_POLICY_TYPE = 'dcae.nodes.policy'
DCAE_POLICIES_TYPE = 'dcae.nodes.policies'
DCAE_POLICY_TYPES = [DCAE_POLICY_TYPE, DCAE_POLICIES_TYPE]
CONFIG_ATTRIBUTES = "configAttributes"


class PolicyHandler(object):
    """talk to policy-handler"""
    SERVICE_NAME_POLICY_HANDLER = "policy_handler"
    X_ECOMP_REQUESTID = 'X-ECOMP-RequestID'
    STATUS_CODE_POLICIES_NOT_FOUND = 404
    DEFAULT_URL = "http://policy-handler"
    _url = None

    @staticmethod
    def _lazy_init():
        """discover policy-handler"""
        if PolicyHandler._url:
            return

        PolicyHandler._url = discover_service_url(PolicyHandler.SERVICE_NAME_POLICY_HANDLER)
        if PolicyHandler._url:
            return

        config = discover_value(DCAE_POLICY_PLUGIN)
        if config and isinstance(config, dict):
            # expected structure for the config value for dcaepolicyplugin key
            # {
            #     "dcaepolicyplugin" : {
            #         "policy_handler" : {
            #             "target_entity" : "policy_handler",
            #             "url" : "http://policy-handler:25577"
            #         }
            #     }
            # }
            PolicyHandler._url = config.get(DCAE_POLICY_PLUGIN, {}) \
                .get(PolicyHandler.SERVICE_NAME_POLICY_HANDLER, {}).get("url")

        if PolicyHandler._url:
            return

        PolicyHandler._url = PolicyHandler.DEFAULT_URL

    @staticmethod
    def get_latest_policy(policy_id):
        """retrieve the latest policy for policy_id from policy-handler"""
        PolicyHandler._lazy_init()

        ph_path = "{0}/policy_latest/{1}".format(PolicyHandler._url, policy_id)
        headers = {PolicyHandler.X_ECOMP_REQUESTID: str(uuid.uuid4())}

        ctx.logger.info("getting latest policy from {0} headers={1}".format(
            ph_path, json.dumps(headers)))
        res = requests.get(ph_path, headers=headers, timeout=60)
        ctx.logger.info("latest policy for policy_id({0}) status({1}) response: {2}"
                        .format(policy_id, res.status_code, res.text))

        if res.status_code == PolicyHandler.STATUS_CODE_POLICIES_NOT_FOUND:
            return

        res.raise_for_status()
        return res.json()

    @staticmethod
    def find_latest_policies(policy_filter):
        """retrieve the latest policies by policy filter (selection criteria) from policy-handler"""
        PolicyHandler._lazy_init()

        ph_path = "{0}/policies_latest".format(PolicyHandler._url)
        headers = {
            PolicyHandler.X_ECOMP_REQUESTID: policy_filter.get(REQUEST_ID, str(uuid.uuid4()))
        }

        ctx.logger.info("finding the latest polices from {0} by {1} headers={2}".format(
            ph_path, json.dumps(policy_filter), json.dumps(headers)))

        res = requests.post(ph_path, json=policy_filter, headers=headers, timeout=60)
        ctx.logger.info("latest policies status({0}) response: {1}"
                        .format(res.status_code, res.text))

        if res.status_code == PolicyHandler.STATUS_CODE_POLICIES_NOT_FOUND:
            return

        res.raise_for_status()
        return res.json().get(LATEST_POLICIES)


def _policy_get():
    """
    dcae.nodes.policy -
    retrieve the latest policy_body for policy_id property
    and save policy_body in runtime_properties
    """
    if DCAE_POLICY_TYPE not in ctx.node.type_hierarchy:
        return

    policy_id = ctx.node.properties.get(POLICY_ID)
    policy_required = ctx.node.properties.get(POLICY_REQUIRED)
    if not policy_id:
        error = "no {0} found in ctx.node.properties".format(POLICY_ID)
        ctx.logger.error(error)
        raise NonRecoverableError(error)

    policy = None
    try:
        policy = PolicyHandler.get_latest_policy(policy_id)
    except Exception as ex:
        error = "failed to get policy({0}): {1}".format(policy_id, str(ex))
        ctx.logger.error("{0}: {1}".format(error, traceback.format_exc()))
        raise NonRecoverableError(error)

    if not policy:
        error = "policy not found for policy_id {0}".format(policy_id)
        ctx.logger.info(error)
        if policy_required:
            raise NonRecoverableError(error)
        return True

    ctx.logger.info("found policy {0}: {1}".format(policy_id, json.dumps(policy)))
    if POLICY_BODY in policy:
        ctx.instance.runtime_properties[POLICY_BODY] = policy[POLICY_BODY]
    return True


def _fix_policy_filter(policy_filter):
    if CONFIG_ATTRIBUTES in policy_filter:
        config_attributes = policy_filter.get(CONFIG_ATTRIBUTES)
        if isinstance(config_attributes, dict):
            return
        try:
            config_attributes = json.loads(config_attributes)
            if config_attributes and isinstance(config_attributes, dict):
                policy_filter[CONFIG_ATTRIBUTES] = config_attributes
                return
        except (ValueError, TypeError):
            pass
        if config_attributes:
            ctx.logger.warn("unexpected %s: %s", CONFIG_ATTRIBUTES, config_attributes)
        del policy_filter[CONFIG_ATTRIBUTES]


def _policies_find():
    """
    dcae.nodes.policies -
    retrieve the latest policies for selection criteria
    and save found policies in runtime_properties
    """
    if DCAE_POLICIES_TYPE not in ctx.node.type_hierarchy:
        return

    policy_required = ctx.node.properties.get(POLICY_REQUIRED)

    try:
        policy_filter = copy.deepcopy(dict(
            (k, v) for (k, v) in dict(ctx.node.properties.get(POLICY_FILTER, {})).iteritems()
            if v or isinstance(v, (int, float))
        ))
        _fix_policy_filter(policy_filter)

        if REQUEST_ID not in policy_filter:
            policy_filter[REQUEST_ID] = str(uuid.uuid4())

        policies_filtered = PolicyHandler.find_latest_policies(policy_filter)

        if not policies_filtered:
            error = "policies not found by {0}".format(json.dumps(policy_filter))
            ctx.logger.info(error)
            if policy_required:
                raise NonRecoverableError(error)
            return True

        ctx.logger.info("found policies by {0}: {1}".format(
            json.dumps(policy_filter), json.dumps(policies_filtered)
        ))
        ctx.instance.runtime_properties[POLICIES_FILTERED] = policies_filtered

    except Exception as ex:
        error = "failed to find policies: {0}".format(str(ex))
        ctx.logger.error("{0}: {1}".format(error, traceback.format_exc()))
        raise NonRecoverableError(error)

    return True


#########################################################
@operation
def policy_get(**kwargs):
    """retrieve the policy or policies and save it in runtime_properties"""
    if ctx.type != NODE_INSTANCE:
        raise NonRecoverableError("can only invoke policy_get on node of types: {0}"
                                  .format(DCAE_POLICY_TYPES))

    if not _policy_get() and not _policies_find():
        error = "unexpected node type {0} for policy_get - expected types: {1}" \
                .format(ctx.node.type_hierarchy, DCAE_POLICY_TYPES)
        ctx.logger.error(error)
        raise NonRecoverableError(error)

    ctx.logger.info("exit policy_get")
