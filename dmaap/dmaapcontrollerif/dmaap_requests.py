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

import requests

### "Constants"
FEEDS_PATH = '/feeds'
PUBS_PATH = '/dr_pubs'
SUBS_PATH = '/dr_subs'
TOPICS_PATH = '/topics'
CLIENTS_PATH = '/mr_clients'
LOCATIONS_PATH = '/dcaeLocations'

class DMaaPControllerHandle(object):
    '''
    A simple wrapper class to map DMaaP bus controller API calls into operations supported by the requests module
    '''

    def __init__(self, api_url, user, password, logger,
                 feeds_path = FEEDS_PATH,
                 pubs_path = PUBS_PATH,
                 subs_path = SUBS_PATH,
                 topics_path = TOPICS_PATH,
                 clients_path = CLIENTS_PATH):
        '''
        Constructor
        '''
        self.api_url = api_url        # URL for the root of the Controller resource tree, no trailing "/"
        self.auth = (user, password)  # user name and password for HTTP basic auth
        self.logger = logger
        self.feeds_path = feeds_path
        self.pubs_path = pubs_path
        self.subs_path = subs_path
        self.topics_path = topics_path
        self.clients_path = clients_path


    ### INTERNAL FUNCTIONS ###

    def _make_url(self, path):
        '''
        Make a full URL given the path relative to the root
        '''
        if not path.startswith('/'):
            path = '/' + path

        return self.api_url + path

    def _get_resource(self, path):
        '''
        Get the DMaaP resource at path, where path is relative to the root.
        '''
        url = self._make_url(path)
        self.logger.info("Querying URL: {0}".format(url))
        return requests.get(url, auth=self.auth)

    def _create_resource(self, path, resource_content):
        '''
        Create a DMaaP resource by POSTing to the resource collection
        identified by path (relative to root), using resource_content as the body of the post
        '''
        url = self._make_url(path)
        self.logger.info("Posting to URL: {0} with body: {1}".format(url, resource_content))
        return requests.post(url, auth=self.auth, json=resource_content)

    def _delete_resource(self, path):
        '''
        Delete the DMaaP resource at path, where path is relative to the root.
        '''
        url = self._make_url(path)
        self.logger.info("Deleting URL: {0}".format(url))
        return requests.delete(url, auth=self.auth)

    ### PUBLIC API ###

    # Data Router Feeds
    def create_feed(self, name, version=None, description=None, aspr_class=None, owner=None, useExisting=None):
        '''
        Create a DMaaP data router feed with the given feed name
        and (optionally) feed version, feed description, ASPR classification,
        owner, and useExisting flag
        '''
        feed_definition = {'feedName' : name}
        if version:
            feed_definition['feedVersion'] = version
        if description:
            feed_definition['feedDescription'] = description
        if aspr_class:
            feed_definition['asprClassification'] = aspr_class
        if owner:
            feed_definition['owner'] = owner
        feeds_path_query = self.feeds_path
        if useExisting == True:                         # It's a boolean!
            feeds_path_query += "?useExisting=true"

        return self._create_resource(feeds_path_query, feed_definition)

    def get_feed_info(self, feed_id):
        '''
        Get the representation of the DMaaP data router feed whose feed id is feed_id.
        '''
        return self._get_resource("{0}/{1}".format(self.feeds_path, feed_id))

    def get_feed_info_by_name(self, feed_name):
        '''
        Get the representation of the DMaaP data router feed whose feed name is feed_name.
        '''
        feeds = self._get_resource("{0}".format(self.feeds_path))
        feed_list = feeds.json()
        for feed in feed_list:
            if feed["feedName"] == feed_name:
                self.logger.info("Found feed with {0}".format(feed_name))
                feed_id = feed["feedId"]
                return self._get_resource("{0}/{1}".format(self.feeds_path, feed_id))

        self.logger.info("feed_name {0} not found".format(feed_name))
        return None

    def delete_feed(self, feed_id):
        '''
        Delete the DMaaP data router feed whose feed id is feed_id.
        '''
        return self._delete_resource("{0}/{1}".format(self.feeds_path, feed_id))

    # Data Router Publishers
    def add_publisher(self, feed_id, location, username, password, status=None):
        '''
        Add a publisher to feed feed_id at location location with user, pass, and status
        '''
        publisher_definition = {
            'feedId' : feed_id,
            'dcaeLocationName' : location,
            'username' : username,
            'userpwd' : password
        }

        if status:
            publisher_definition['status'] = status

        return self._create_resource(self.pubs_path, publisher_definition)

    def get_publisher_info(self, pub_id):
        '''
        Get the representation of the DMaaP data router publisher whose publisher id is pub_id
        '''
        return self._get_resource("{0}/{1}".format(self.pubs_path, pub_id))

    def delete_publisher(self, pub_id):
        '''
        Delete the DMaaP data router publisher whose publisher id is id.
        '''
        return self._delete_resource("{0}/{1}".format(self.pubs_path, pub_id))


    # Data Router SUbscrihers
    def add_subscriber(self, feed_id, location, delivery_url, username, password, decompress, privileged, status=None):
        '''
        Add a publisher to feed feed_id at location location with user, pass, and status
        '''
        subscriber_definition = {
            'feedId' : feed_id,
            'dcaeLocationName' : location,
            'deliveryURL' : delivery_url,
            'username' : username,
            'userpwd' : password,
            'decompress': decompress,
            'privilegedSubscriber': privileged
        }

        if status:
            subscriber_definition['status'] = status

        return self._create_resource(self.subs_path, subscriber_definition)

    def get_subscriber_info(self, sub_id):
        '''
        Get the representation of the DMaaP data router subscriber whose subscriber id is sub_id
        '''
        return self._get_resource("{0}/{1}".format(self.subs_path, sub_id))

    def delete_subscriber(self, sub_id):
        '''
        Delete the DMaaP data router subscriber whose subscriber id is sub_id.
        '''
        return self._delete_resource("{0}/{1}".format(self.subs_path, sub_id))

    # Message router topics
    def create_topic(self, name, description = None, txenable = None, owner = None, replication_case = None, global_mr_url = None, useExisting = None):
        '''
        Create a message router topic with the topic name 'name' and optionally the topic_description
        'description', the 'txenable' flag, the 'useExisting' flag and the topic owner 'owner'.
        '''
        topic_definition = {'topicName' : name}
        if description:
            topic_definition['topicDescription'] = description
        if owner:
            topic_definition['owner'] = owner
        if txenable != None:                            # It's a boolean!
            topic_definition['txenable'] = txenable
        if replication_case:
            topic_definition['replicationCase'] = replication_case
        if global_mr_url:
            topic_definition['globalMrURL'] = global_mr_url
        topics_path_query = self.topics_path
        if useExisting == True:                         # It's a boolean!
            topics_path_query += "?useExisting=true"

        return self._create_resource(topics_path_query, topic_definition)

    def get_topic_info(self, fqtn):
        '''
        Get information about the topic whose fully-qualified name is 'fqtn'
        '''
        return self._get_resource("{0}/{1}".format(self.topics_path, fqtn))

    def get_topic_fqtn_by_name(self, topic_name):
        '''
        Get the representation of the DMaaP message router topic fqtn whose topic name is topic_name.
        '''
        topics = self._get_resource("{0}".format(self.topics_path))
        topic_list = topics.json()
        for topic in topic_list:
            if topic["topicName"] == topic_name:
                self.logger.info("Found existing topic with name {0}".format(topic_name))
                fqtn = topic["fqtn"]
                return fqtn

        self.logger.info("topic_name {0} not found".format(topic_name))
        return None

    def delete_topic(self, fqtn):
        '''
        Delete the topic whose fully qualified name is 'fqtn'
        '''
        return self._delete_resource("{0}/{1}".format(self.topics_path, fqtn))

    # Message route clients (publishers and subscribers
    def create_client(self, fqtn, location, client_role, actions):
        '''
        Creates a client authorized to access the topic with fully-qualified name 'fqtn',
        from the location 'location', using the AAF client role 'client_role'.  The
        client is authorized to perform actions in the list 'actions'.  (Valid
        values are 'pub', 'sub', and 'view'
        '''
        client_definition = {
            'fqtn' : fqtn,
            'dcaeLocationName' : location,
            'clientRole' : client_role,
            'action' : actions
        }
        return self._create_resource(self.clients_path, client_definition)

    def get_client_info(self, client_id):
        '''
        Get client information for the client whose client ID is 'client_id'
        '''
        return self._get_resource("{0}/{1}".format(self.clients_path, client_id))

    def delete_client(self, client_id):
        '''
        Delete the client whose client ID is 'client_id'
        '''
        return self._delete_resource("{0}/{1}".format(self.clients_path, client_id))

    def get_dcae_locations(self, dcae_layer):
        '''
        Get the list of location names known to the DMaaP bus controller
        whose "dcaeLayer" property matches dcae_layer and whose status is "VALID".
        '''
        # Do these as a separate step so things like 404 get reported precisely
        locations = self._get_resource(LOCATIONS_PATH)
        locations.raise_for_status()

        # pull out location names for VALID locations with matching dcae_layer
        return [location["dcaeLocationName"] for location in locations.json()
                if location['dcaeLayer'] == dcae_layer
                and location['status'] == 'VALID']

    def get_dcae_central_locations(self):
        '''
        Get the list of location names known to the DMaaP bus controller
        whose "dcaeLayer" property contains "central" (ignoring case)
        and whose status is "VALID".
        "dcaeLayer" contains "central" for central sites.
        '''
        # Do these as a separate step so things like 404 get reported precisely
        locations = self._get_resource(LOCATIONS_PATH)
        locations.raise_for_status()

        # pull out location names for VALID central locations
        return [location["dcaeLocationName"] for location in locations.json()
                if 'central' in location['dcaeLayer'].lower()
                and location['status'] == 'VALID']

