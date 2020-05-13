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
from dmaapplugin import DMAAP_API_URL, DMAAP_USER, DMAAP_PASS
from dmaapplugin.dmaaputils import random_string
from dmaapcontrollerif.dmaap_requests import DMaaPControllerHandle

# Set up a subscriber to a source feed
def _set_up_subscriber(dmc, source_feed_id, loc, delivery_url, username, userpw):
    # Add subscriber to source feed
    add_sub = dmc.add_subscriber(source_feed_id, loc, delivery_url, username, userpw)
    add_sub.raise_for_status()
    return add_sub.json()

# Set up a publisher to a target feed
def _set_up_publisher(dmc, target_feed_id, loc):
    username = random_string(8)
    userpw = random_string(16)
    add_pub = dmc.add_publisher(target_feed_id, loc, username, userpw)
    add_pub.raise_for_status()
    pub_info = add_pub.json()
    return pub_info["pubId"], username, userpw

# Get a central location to use when creating a publisher or subscriber
def _get_central_location(dmc):
    locations = dmc.get_dcae_central_locations()
    if len(locations) < 1:
        raise Exception('No central location found for setting up DR bridging')
    return locations[0]          # We take the first one.  Typically there will be two central locations


# Set up a "bridge" between two feeds internal to DCAE
# A source feed "bridges_to" a target feed, meaning that anything published to
# the source feed will be delivered to subscribers to the target feed (as well as
# to subscribers of the source feed).
#
# The bridge is established by first adding a publisher to the target feed.  The result of doing this
# is a publish URL and a set of publication credentials.
#The publish URL and publication credentials are used to set up a subscriber to the source feed.
#I.e., we tell the source feed to deliver to an endpoint which is actually a publish
# endpoint for the target feed.
@operation
def create_dr_bridge(**kwargs):

    try:

        # Get source and target feed ids
        if 'feed_id' in ctx.target.instance.runtime_properties:
            target_feed_id = ctx.target.instance.runtime_properties['feed_id']
        else:
            raise Exception('Target feed has no feed_id property')
        if 'feed_id' in ctx.source.instance.runtime_properties:
            source_feed_id = ctx.source.instance.runtime_properties['feed_id']
        else:
            raise Exception('Source feed has no feed_id property')

        dmc = DMaaPControllerHandle(DMAAP_API_URL, DMAAP_USER, DMAAP_PASS, ctx.logger)

        # Get a location to use when creating a publisher or subscriber--a central location seems reasonable
        loc = _get_central_location(dmc)

        ctx.logger.info('Creating bridge from feed {0} to feed {1} using location {2}'.format(source_feed_id, target_feed_id, loc))

        # Add publisher to target feed
        publisher_id, username, userpw = _set_up_publisher(dmc, target_feed_id, loc)
        ctx.logger.info("Added publisher id {0} to  target feed {1} with user {2}".format(publisher_id, target_feed_id, username))

        # Add subscriber to source feed
        delivery_url = ctx.target.instance.runtime_properties['publish_url']
        subscriber_info = _set_up_subscriber(dmc, source_feed_id, loc, delivery_url, username, userpw)
        subscriber_id = subscriber_info["subId"]
        ctx.logger.info("Added subscriber id {0} to source feed {1} with delivery url {2}".format(subscriber_id, source_feed_id, delivery_url))

        # Save the publisher and subscriber IDs on the source node, indexed by the target node id
        ctx.source.instance.runtime_properties[ctx.target.node.id] = {"publisher_id": publisher_id, "subscriber_id": subscriber_id}

    except Exception as e:
        ctx.logger.error("Error creating bridge: {0}".format(e))
        raise NonRecoverableError(e)

# Set up a bridge from an internal DCAE feed to a feed in an external Data Router system
# The target feed needs to be provisioned in the external Data Router system.  A publisher
# to that feed must also be set up in the external Data Router system.  The publish URL,
# username, and password need to be captured in a target node of type dcae.nodes.ExternalTargetFeed.
# The bridge is established by setting up a subscriber to the internal DCAE source feed using the
# external feed publisher parameters as delivery parameters for the subscriber.
@operation
def create_external_dr_bridge(**kwargs):
    try:

        # Make sure target feed has full set of properties
        if 'url' in ctx.target.node.properties and 'username' in ctx.target.node.properties and 'userpw' in ctx.target.node.properties:
            url = ctx.target.node.properties['url']
            username = ctx.target.node.properties['username']
            userpw = ctx.target.node.properties['userpw']
        else:
            raise Exception ("Target feed missing url, username, and/or user pw")

        # Make sure source feed has a feed ID
        if 'feed_id' in ctx.source.instance.runtime_properties:
            source_feed_id = ctx.source.instance.runtime_properties['feed_id']
        else:
            raise Exception('Source feed has no feed_id property')

        dmc = DMaaPControllerHandle(DMAAP_API_URL, DMAAP_USER, DMAAP_PASS, ctx.logger)

        # Get a central location to use when creating subscriber
        loc = _get_central_location(dmc)

        ctx.logger.info('Creating external bridge from feed {0} to external url {1} using location {2}'.format(source_feed_id, url, loc))

        # Create subscription to source feed using properties of the external target feed
        subscriber_info = _set_up_subscriber(dmc, source_feed_id, loc, url, username, userpw)
        subscriber_id = subscriber_info["subId"]
        ctx.logger.info("Added subscriber id {0} to source feed {1} with delivery url {2}".format(subscriber_id, source_feed_id, url))

        # Save the subscriber ID on the source node, indexed by the target node id
        ctx.source.instance.runtime_properties[ctx.target.node.id] = {"subscriber_id": subscriber_id}

    except Exception as e:
        ctx.logger.error("Error creating external bridge: {0}".format(e))
        raise NonRecoverableError(e)

# Set up a bridge from a feed in an external Data Router system to an internal DCAE feed.
# The bridge is established by creating a publisher on the internal DCAE feed.  Then a subscription
# to the external feed is created through manual provisioning in the external Data Router system, using
# the publish URL and the publisher username and password for the internal feed as the delivery parameters
# for the external subscription.
# In order to obtain the publish URL, publisher username, and password, a blueprint using this sort of
# bridge will typically have an output that exposes the runtime_property set on the source node in this operation.
@operation
def create_external_source_dr_bridge(**kwargs):
    try:
        # Get target feed id
        if 'feed_id' in ctx.target.instance.runtime_properties:
            target_feed_id = ctx.target.instance.runtime_properties['feed_id']
        else:
            raise Exception('Target feed has no feed_id property')

        dmc = DMaaPControllerHandle(DMAAP_API_URL, DMAAP_USER, DMAAP_PASS, ctx.logger)

        # Get a central location to use when creating a publisher
        loc = _get_central_location(dmc)

        # Create a publisher on the target feed
        publisher_id, username, userpw = _set_up_publisher(dmc, target_feed_id, loc)

        # Save the publisher info on the source node, indexed by the target node
        ctx.source.instance.runtime_properties[ctx.target.node.id] = {"publisher_id": publisher_id, "url": ctx.target.instance.runtime_properties["publish_url"], "username": username, "userpw": userpw}

    except Exception as e:
        ctx.logger.error("Error creating external source bridge: {0}".format(e))

# Remove the bridge between the relationship source and target.
# For a bridge between 2 internal feeds, deletes the subscriber on the source feed and the publisher on the target feed.
# For a bridge to an external target feed, deletes the subscriber on the source feed.
# For a bridge from an external source feed, deletes the publisher on the target feed.
@operation
def remove_dr_bridge(**kwargs):
    try:

        dmc = DMaaPControllerHandle(DMAAP_API_URL, DMAAP_USER, DMAAP_PASS, ctx.logger)

        if ctx.target.node.id in ctx.source.instance.runtime_properties:

            if 'subscriber_id' in ctx.source.instance.runtime_properties[ctx.target.node.id]:
                # Delete the subscription for this bridge
                ctx.logger.info("Removing bridge -- deleting subscriber {0}".format(ctx.source.instance.runtime_properties[ctx.target.node.id]['subscriber_id']))
                dmc.delete_subscriber(ctx.source.instance.runtime_properties[ctx.target.node.id]['subscriber_id'])

            if 'publisher_id' in ctx.source.instance.runtime_properties:
                # Delete the publisher for this bridge
                ctx.logger.info("Removing bridge -- deleting publisher {0}".format(ctx.source.instance.runtime_properties[ctx.target.node.id]['publisher_id']))
                dmc.delete_publisher(ctx.source.instance.runtime_properties[ctx.target.node.id]['publisher_id'])

        ctx.logger.info("Remove bridge from {0} to {1}".format(ctx.source.node.id, ctx.target.node.id))

    except Exception as e:
        ctx.logger.error("Error removing bridge: {0}".format(e))
        # Let the uninstall workflow proceed--don't throw a NonRecoverableError
