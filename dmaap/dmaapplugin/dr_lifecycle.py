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

# Lifecycle operations for DMaaP Data Router feeds

@operation
def create_feed(**kwargs):
    '''
    Create a new data router feed
        Expects "feed_name" to be set in node properties
        If 'feed_name' is not set or is empty, generates a random one.
        Allows "feed_version", "feed_description", "aspr_classification" and "useExisting" as optional properties
        (Sets default values if not provided )
        Sets instance runtime properties:
        Note that 'useExisting' is a flag indicating whether DBCL will use existing feed if the feed already exists.
            - "feed_id"
            - "publish_url"
            - "log_url"

    '''
    try:
        # Make sure there's a feed_name
        feed_name = ctx.node.properties.get("feed_name")
        if not (feed_name and feed_name.strip()):
            feed_name = random_string(12)

        # Set defaults/placeholders for the optional properties for the feed
        if "feed_version" in ctx.node.properties:
            feed_version = ctx.node.properties["feed_version"]
        else:
            feed_version = "0.0"
        if "feed_description" in ctx.node.properties:
            feed_description = ctx.node.properties["feed_description"]
        else:
            feed_description = "No description provided"
        if "aspr_classification" in ctx.node.properties:
            aspr_classification = ctx.node.properties["aspr_classification"]
        else:
            aspr_classification = "unclassified"
        if "useExisting" in ctx.node.properties:
            useExisting = ctx.node.properties["useExisting"]
        else:
            useExisting = False

        # Make the request to the controller
        dmc = DMaaPControllerHandle(DMAAP_API_URL, DMAAP_USER, DMAAP_PASS, ctx.logger)
        ctx.logger.info("Attempting to create feed name {0}".format(feed_name))
        f = dmc.create_feed(feed_name, feed_version, feed_description, aspr_classification, DMAAP_OWNER, useExisting)
        f.raise_for_status()

        # Capture important properties from the result
        feed = f.json()
        ctx.instance.runtime_properties["feed_id"] = feed["feedId"]
        ctx.instance.runtime_properties["publish_url"] = feed["publishURL"]
        ctx.instance.runtime_properties["log_url"] = feed["logURL"]
        ctx.logger.info("Created feed name {0} with feed id {1}".format(feed_name, feed["feedId"]))

    except Exception as e:
        ctx.logger.error("Error creating feed: {er}".format(er=e))
        raise NonRecoverableError(e)


@operation
def get_existing_feed(**kwargs):
    '''
    Find information for an existing data router feed
        Expects "feed_id" to be set in node properties -- uniquely identifies the feed
        Sets instance runtime properties:
            - "feed_id"
            - "publish_url"
            - "log_url"
    '''

    try:
        # Make the lookup request to the controller
        dmc = DMaaPControllerHandle(DMAAP_API_URL, DMAAP_USER, DMAAP_PASS, ctx.logger)
        ctx.logger.info("DMaaPControllerHandle() returned")
        feed_id_input = False
        if "feed_id" in ctx.node.properties:
            feed_id_input = True
            f = dmc.get_feed_info(ctx.node.properties["feed_id"])
        elif "feed_name" in ctx.node.properties:
            feed_name = ctx.node.properties["feed_name"]
            f = dmc.get_feed_info_by_name(feed_name)
            if f is None:
                ctx.logger.error("Not find existing feed with feed name {0}".format(feed_name))
                raise ValueError("Not find existing feed with feed name " + feed_name)
        else:
            raise ValueError("Either feed_id or feed_name must be defined to get existing feed")

        f.raise_for_status()

        # Capture important properties from the result
        feed = f.json()
        feed_id = feed["feedId"]
        ctx.instance.runtime_properties["feed_id"] = feed_id   # Just to be consistent with newly-created node, above
        ctx.instance.runtime_properties["publish_url"] = feed["publishURL"]
        ctx.instance.runtime_properties["log_url"] = feed["logURL"]
        if feed_id_input:
            ctx.logger.info("Found existing feed with feed id {0}".format(ctx.node.properties["feed_id"]))
        else:
            ctx.logger.info("Found existing feed with feed name {0}".format(ctx.node.properties["feed_name"]))

    except ValueError as e:
        ctx.logger.error("{er}".format(er=e))
        raise NonRecoverableError(e)
    except Exception as e:
        if feed_id_input:
            ctx.logger.error("Error getting existing feed id {id}: {er}".format(id=ctx.node.properties["feed_id"],er=e))
        else:
            ctx.logger.error("Error getting existing feed name {name}: {er}".format(name=ctx.node.properties["feed_name"],er=e))
        raise NonRecoverableError(e)


@operation
def delete_feed(**kwargs):
    '''
    Delete a feed
        Expects "feed_id" to be set on the instance's runtime properties
    '''
    try:
        # Make the lookup request to the controllerid=ctx.node.properties["feed_id"]
        dmc = DMaaPControllerHandle(DMAAP_API_URL, DMAAP_USER, DMAAP_PASS, ctx.logger)
        f = dmc.delete_feed(ctx.instance.runtime_properties["feed_id"])
        f.raise_for_status()
        ctx.logger.info("Deleting feed id {0}".format(ctx.instance.runtime_properties["feed_id"]))

    except Exception as e:
        ctx.logger.error("Error deleting feed id {id}: {er}".format(id=ctx.instance.runtime_properties["feed_id"],er=e))
        # don't raise a NonRecoverable error here--let the uninstall workflow continue
