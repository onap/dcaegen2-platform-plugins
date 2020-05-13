# ============LICENSE_START====================================================
# org.onap.ccsdk
# =============================================================================
# Copyright (c) 2017-2019 AT&T Intellectual Property. All rights reserved.
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
from dmaapplugin import DMAAP_API_URL, DMAAP_USER, DMAAP_PASS, DMAAP_OWNER, CONSUL_HOST
from dmaapcontrollerif.dmaap_requests import DMaaPControllerHandle
from consulif.consulif import ConsulHandle

# Message router relationship operations

def _add_mr_client(ctype, actions):
    '''
    Adds the node represented by 'source' as a client (publisher or subscriber) to
    to topic represented by the 'target' node.  The list of actions in 'actions'
    determines whether the client is a subscriber or a publisher.

    Assumes target (the topic) has the following runtime property set
        - fqtn
    Assumes source (the client) has a runtime property whose name matches the node name of the feed.
    This is a dictionary containing the following properties:
        - location   (the dcaeLocationName to pass when adding the client to the topic)
        - client_role (the AAF client role under which the client will access the topic)
    Adds two properties to the dictionary above:
        - topic_url (the URL that the client can use to access the topic)
        - client_id  (used to delete the client in the uninstall workflow)
    '''
    try:
        # Make sure we have a name under which to store DMaaP configuration
        # Check early so we don't needlessly create DMaaP entities
        if 'service_component_name' not in ctx.source.instance.runtime_properties:
            raise Exception("Source node does not have 'service_component_name' in runtime_properties")

        target_topic = ctx.target.node.id           # Key for the source's dictionary with topic-related info
        fqtn = ctx.target.instance.runtime_properties["fqtn"]
        ctx.logger.info("Attempting to add {0} as {1} to topic {2}".format(ctx.source.node.id, ctype, fqtn))

        # Get the parameters needed for adding the client
        location = ctx.source.instance.runtime_properties[target_topic]["location"]
        client_role = ctx.source.instance.runtime_properties[target_topic]["client_role"]

        # Make the request to add the client to the topic
        dmc = DMaaPControllerHandle(DMAAP_API_URL, DMAAP_USER, DMAAP_PASS, ctx.logger)
        c = dmc.create_client(fqtn, location, client_role, actions)
        c.raise_for_status()
        client_info = c.json()
        client_id = client_info["mrClientId"]
        topic_url = client_info["topicURL"]

        # Update source's runtime properties
        #ctx.source.instance.runtime_properties[target_topic]["topic_url"] = topic_url
        #ctx.source.instance.runtime_properties[target_topic]["client_id"] = client_id
        ctx.source.instance.runtime_properties[target_topic] = {
            "topic_url" : topic_url,
            "client_id" : client_id,
            "location" : location,
            "client_role" : client_role
        }

        ctx.logger.info("Added {0} id {1} to feed {2} at {3}".format(ctype, client_id, fqtn, location))

        # Set key in Consul
        ch = ConsulHandle("http://{0}:8500".format(CONSUL_HOST), None, None, ctx.logger)
        ch.add_to_entry("{0}:dmaap".format(ctx.source.instance.runtime_properties['service_component_name']), target_topic, ctx.source.instance.runtime_properties[target_topic])

    except Exception as e:
        ctx.logger.error("Error adding client to feed: {er}".format(er=e))
        raise NonRecoverableError(e)

@operation
def add_mr_publisher(**kwargs):
    _add_mr_client("publisher", ["view", "pub"])

@operation
def add_mr_subscriber(**kwargs):
        _add_mr_client("subscriber", ["view", "sub"])

@operation
def delete_mr_client(**kwargs):
    '''
    Delete the client (publisher or subscriber).
    Expect property 'client_id' to have been set in the instance's runtime_properties
    when the client was created.
    '''
    try:
        target_topic = ctx.target.node.id
        client_id = ctx.source.instance.runtime_properties[target_topic]["client_id"]
        ctx.logger.info("Attempting to delete client {0} ".format(client_id))
        dmc = DMaaPControllerHandle(DMAAP_API_URL, DMAAP_USER, DMAAP_PASS, ctx.logger)
        c = dmc.delete_client(client_id)
        c.raise_for_status()

        ctx.logger.info("Deleted client {0}".format(client_id))

        # Attempt to remove the entire ":dmaap" entry from the Consul KV store
        # Will quietly do nothing if the entry has already been removed
        ch = ConsulHandle("http://{0}:8500".format(CONSUL_HOST), None, None, ctx.logger)
        ch.delete_entry("{0}:dmaap".format(ctx.source.instance.runtime_properties['service_component_name']))

    except Exception as e:
        ctx.logger.error("Error deleting MR client: {er}".format(er=e))
        # don't raise a NonRecoverable error here--let the uninstall workflow continue

