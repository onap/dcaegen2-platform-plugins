# ============LICENSE_START====================================================
# org.onap.ccsdk
# =============================================================================
# Copyright (c) 2017-2019 AT&T Intellectual Property. All rights reserved.
# Copyright (c) 2020 Pantheon.tech. All rights reserved.
# =============================================================================
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
# ============LICENSE_END======================================================

from cloudify import ctx
from cloudify.decorators import operation
from cloudify.exceptions import NonRecoverableError
from dmaapplugin import DMAAP_API_URL, DMAAP_USER, DMAAP_PASS, DMAAP_OWNER
from dmaapplugin.dmaaputils import random_string
from dmaapcontrollerif.dmaap_requests import DMaaPControllerHandle

# Lifecycle operations for DMaaP Message Router topics
@operation
def create_topic(**kwargs):
    '''
    Creates a message router topic.
    Allows 'topic_name', 'topic_description', 'txenable', 'replication_case', 'global_mr_url',
    and 'useExisting' as optional node properties.  If 'topic_name' is not set,
    generates a random one.
    Sets 'fqtn' in the instance runtime_properties.
    Note that 'txenable' is a Message Router flag indicating whether transactions
    are enabled on the topic.
    Note that 'useExisting' is a flag indicating whether DBCL will use existing topic if
    the topic already exists.
    '''
    try:
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

        if "useExisting" in ctx.node.properties:
            useExisting = ctx.node.properties["useExisting"]
        else:
            useExisting = False

        # Make the request to the controller
        dmc = DMaaPControllerHandle(DMAAP_API_URL, DMAAP_USER, DMAAP_PASS, ctx.logger)
        ctx.logger.info("Attempting to create topic name {0}".format(topic_name))
        t = dmc.create_topic(topic_name, topic_description, txenable, DMAAP_OWNER, replication_case, global_mr_url, useExisting)
        t.raise_for_status()

        # Capture important properties from the result
        topic = t.json()
        ctx.instance.runtime_properties["fqtn"] = topic["fqtn"]

    except Exception as e:
        ctx.logger.error("Error creating topic: {er}".format(er=e))
        raise NonRecoverableError(e)

@operation
def get_existing_topic(**kwargs):
    '''
    Get data for an existing topic.
    Expects 'fqtn' as a node property.
    Copies this property to 'fqtn' in runtime properties for consistency
    with a newly-created topic.
    While there's no real need to make a call to the DMaaP bus controller,
    we do so just to make sure the fqtn is known to the controller, so we
    don't run into problems when we try to add a publisher or subscriber later.
    '''
    try:
        dmc = DMaaPControllerHandle(DMAAP_API_URL, DMAAP_USER, DMAAP_PASS, ctx.logger)
        fqtn_input = False
        if "fqtn" in ctx.node.properties:
            fqtn = ctx.node.properties["fqtn"]
            fqtn_input = True
        elif "topic_name" in ctx.node.properties:
            topic_name = ctx.node.properties["topic_name"]
            ctx.logger.info("Attempting to get fqtn for existing topic {0}".format(topic_name))
            fqtn = dmc.get_topic_fqtn_by_name(topic_name)
            if fqtn is None:
                raise ValueError("Not find existing topic with name " + topic_name)
        else:
            ctx.logger.error("Not find existing topic with name {0}".format(topic_name))
            raise ValueError("Either fqtn or topic_name must be defined to get existing topic")

        ctx.logger.info("Attempting to get info for existing topic {0}".format(fqtn))
        t = dmc.get_topic_info(fqtn)
        t.raise_for_status()

        ctx.instance.runtime_properties["fqtn"] = fqtn

    except Exception as e:
        ctx.logger.error("Error getting existing topic: {er}".format(er=e))
        raise NonRecoverableError(e)

@operation
def delete_topic(**kwargs):
    '''
    Delete the topic.  Expects the instance runtime property "fqtn" to have been
    set when the topic was created.
    '''
    try:
        fqtn = ctx.instance.runtime_properties["fqtn"]
        dmc = DMaaPControllerHandle(DMAAP_API_URL, DMAAP_USER, DMAAP_PASS, ctx.logger)
        ctx.logger.info("Attempting to delete topic {0}".format(fqtn))
        t = dmc.delete_topic(fqtn)
        t.raise_for_status()

    except Exception as e:
        ctx.logger.error("Error getting existing topic: {er}".format(er=e))
        # don't raise a NonRecoverable error here--let the uninstall workflow continue
