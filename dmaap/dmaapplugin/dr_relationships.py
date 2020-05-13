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
from dmaapplugin import DMAAP_API_URL, DMAAP_USER, DMAAP_PASS, CONSUL_HOST
from dmaapplugin.dmaaputils import random_string
from dmaapcontrollerif.dmaap_requests import DMaaPControllerHandle
from consulif.consulif import ConsulHandle

# Lifecycle operations for DMaaP Data Router
# publish and subscribe relationships

@operation
def add_dr_publisher(**kwargs):
    '''
    Sets up the source of the publishes_relationship as a publisher to the feed that
    is the target of the relationship
        Assumes target (the feed) has the following runtime properties set
            - feed_id
            - log_url
            - publish_url
        Assumes source (the publisher) has a runtime property whose name matches the node name of the feed.
        This is a dictionary containing one property:
            - location   (the dcaeLocationName to pass when adding the publisher to the feed)
        Generates a user name and password that the publisher will need to use when publishing
        Adds the following properties to the dictionary above:
             - publish_url
             - log_url
             - username
             - password
    '''
    try:
        # Make sure we have a name under which to store DMaaP configuration
        # Check early so we don't needlessly create DMaaP entities
        if 'service_component_name' not in ctx.source.instance.runtime_properties:
            raise Exception("Source node does not have 'service_component_name' in runtime_properties")

        target_feed = ctx.target.node.id
        ctx.logger.info("Attempting to add publisher {0} to feed {1}".format(ctx.source.node.id, target_feed))

        # Set up the parameters for the add_publisher request to the DMaaP bus controller
        feed_id = ctx.target.instance.runtime_properties["feed_id"]
        location = ctx.source.instance.runtime_properties[target_feed]["location"]
        username = random_string(8)
        password = random_string(16)

        # Make the request to add the publisher to the feed
        dmc = DMaaPControllerHandle(DMAAP_API_URL, DMAAP_USER, DMAAP_PASS, ctx.logger)
        add_pub = dmc.add_publisher(feed_id, location, username, password)
        add_pub.raise_for_status()
        publisher_info = add_pub.json()
        publisher_id = publisher_info["pubId"]
        ctx.logger.info("Added publisher id {0} to feed {1} at {2}, with user {3}, pass {4}".format(publisher_id, feed_id, location, username, password))

        # Set runtime properties on the source
        ctx.source.instance.runtime_properties[target_feed] = {
           "publisher_id" : publisher_id,
           "location" : location,
           "publish_url" : ctx.target.instance.runtime_properties["publish_url"],
           "log_url" : ctx.target.instance.runtime_properties["log_url"],
           "username" : username,
           "password" : password
        }

        # Set key in Consul
        ch = ConsulHandle("http://{0}:8500".format(CONSUL_HOST), None, None, ctx.logger)
        cpy = dict(ctx.source.instance.runtime_properties[target_feed])
        ch.add_to_entry("{0}:dmaap".format(ctx.source.instance.runtime_properties['service_component_name']), target_feed, cpy)

    except Exception as e:
        ctx.logger.error("Error adding publisher to feed: {er}".format(er=e))
        raise NonRecoverableError(e)


@operation
def delete_dr_publisher(**kwargs):
    '''
    Deletes publisher (the source of the publishes_files relationship)
    from the feed (the target of the relationship).
    Assumes that the 'publisher_id' property was added to the dictionary of feed-related properties,
    when the publisher was added to the feed.
    '''

    try:
        # Make sure we have a name under which to store DMaaP configuration
        # Check early so we don't needlessly create DMaaP entities
        if 'service_component_name' not in ctx.source.instance.runtime_properties:
            raise Exception("Source node does not have 'service_component_name' in runtime_properties")

        # Get the publisher id
        target_feed = ctx.target.node.id
        publisher_id = ctx.source.instance.runtime_properties[target_feed]["publisher_id"]
        ctx.logger.info("Attempting to delete publisher {0}".format(publisher_id))

        # Make the request
        dmc = DMaaPControllerHandle(DMAAP_API_URL, DMAAP_USER, DMAAP_PASS, ctx.logger)
        del_result = dmc.delete_publisher(publisher_id)
        del_result.raise_for_status()

        ctx.logger.info("Deleted publisher {0}".format(publisher_id))

        # Attempt to remove the entire ":dmaap" entry from the Consul KV store
        # Will quietly do nothing if the entry has already been removed
        ch = ConsulHandle("http://{0}:8500".format(CONSUL_HOST), None, None, ctx.logger)
        ch.delete_entry("{0}:dmaap".format(ctx.source.instance.runtime_properties['service_component_name']))

    except Exception as e:
        ctx.logger.error("Error deleting publisher: {er}".format(er=e))
        # don't raise a NonRecoverable error here--let the uninstall workflow continue


@operation
def add_dr_subscriber(**kwargs):
    '''
    Sets up the source of the subscribes_to_files relationship as a subscriber to the
    feed that is the target of the relationship.
    Assumes target (the feed) has the following runtime property set
        - feed_id
    Assumes source (the subscriber) has a runtime property whose name matches the node name of the feed.
    This is a dictionary containing the following properties:
        - location   (the dcaeLocationName to pass when adding the publisher to the feed)
        - delivery_url (the URL to which data router will deliver files)
        - username (the username data router will use when delivering files)
        - password (the password data router will use when delivering files)
    Adds a property to the dictionary above:
        - subscriber_id  (used to delete the subscriber in the uninstall workflow
    '''
    try:
        target_feed = ctx.target.node.id
        ctx.logger.info("Attempting to add subscriber {0} to feed {1}".format(ctx.source.node.id, target_feed))

        # Get the parameters for the call
        feed_id = ctx.target.instance.runtime_properties["feed_id"]
        feed = ctx.source.instance.runtime_properties[target_feed]
        location = feed["location"]
        delivery_url = feed["delivery_url"]
        username = feed["username"]
        password = feed["password"]
        decompress = feed["decompress"] if "decompress" in feed else False
        privileged = feed["privileged"] if "privileged" in feed else False

        # Make the request to add the subscriber to the feed
        dmc = DMaaPControllerHandle(DMAAP_API_URL, DMAAP_USER, DMAAP_PASS, ctx.logger)
        add_sub = dmc.add_subscriber(feed_id, location, delivery_url,username, password, decompress, privileged)
        add_sub.raise_for_status()
        subscriber_info = add_sub.json()
        subscriber_id = subscriber_info["subId"]
        ctx.logger.info("Added subscriber id {0} to feed {1} at {2}".format(subscriber_id, feed_id, location))

        # Add subscriber_id to the runtime properties
        # ctx.source.instance.runtime_properties[target_feed]["subscriber_id"] = subscriber_id
        ctx.source.instance.runtime_properties[target_feed] = {
            "subscriber_id": subscriber_id,
            "location" : location,
            "delivery_url" : delivery_url,
            "username" : username,
            "password" : password,
            "decompress": decompress,
            "privilegedSubscriber": privileged
        }
        ctx.logger.info("on source: {0}".format(ctx.source.instance.runtime_properties[target_feed]))

        # Set key in Consul
        ch = ConsulHandle("http://{0}:8500".format(CONSUL_HOST), None, None, ctx.logger)
        cpy = dict(ctx.source.instance.runtime_properties[target_feed])
        ch.add_to_entry("{0}:dmaap".format(ctx.source.instance.runtime_properties['service_component_name']), target_feed, cpy)

    except Exception as e:
        ctx.logger.error("Error adding subscriber to feed: {er}".format(er=e))
        raise NonRecoverableError(e)


@operation
def delete_dr_subscriber(**kwargs):
    '''
    Deletes subscriber (the source of the subscribes_to_files relationship)
    from the feed (the target of the relationship).
    Assumes that the source node's runtime properties dictionary for the target feed
    includes 'subscriber_id', set when the publisher was added to the feed.
    '''
    try:
        # Get the subscriber id
        target_feed = ctx.target.node.id
        subscriber_id = ctx.source.instance.runtime_properties[target_feed]["subscriber_id"]
        ctx.logger.info("Attempting to delete subscriber {0} from feed {1}".format(subscriber_id, target_feed))

        # Make the request
        dmc = DMaaPControllerHandle(DMAAP_API_URL, DMAAP_USER, DMAAP_PASS, ctx.logger)
        del_result = dmc.delete_subscriber(subscriber_id)
        del_result.raise_for_status()

        ctx.logger.info("Deleted subscriber {0}".format(subscriber_id))

        # Attempt to remove the entire ":dmaap" entry from the Consul KV store
        # Will quietly do nothing if the entry has already been removed
        ch = ConsulHandle("http://{0}:8500".format(CONSUL_HOST), None, None, ctx.logger)
        ch.delete_entry("{0}:dmaap".format(ctx.source.instance.runtime_properties['service_component_name']))

    except Exception as e:
        ctx.logger.error("Error deleting subscriber: {er}".format(er=e))
        # don't raise a NonRecoverable error here--let the uninstall workflow continue
