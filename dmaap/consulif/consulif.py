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

import consul
import json
try:
    from urllib.parse import urlparse
except ImportError:
    from urlparse import urlparse


class ConsulHandle(object):
    '''
    Provide access to Consul KV store and service discovery
    '''

    def __init__(self, api_url, user, password, logger):
        '''
        Constructor
        '''
        u = urlparse(api_url)
        self.ch = consul.Consul(host=u.hostname, port=u.port, scheme=u.scheme)

    def get_config(self, key):
        '''
        Get configuration information from Consul using the provided key.
        It should be in JSON form.  Convert it to a dictionary
        '''
        (index, val) = self.ch.kv.get(key)
        config = json.loads(val['Value'])        # will raise ValueError if not JSON, let it propagate
        return config

    def get_service(self,service_name):
        '''
        Look up the service named service_name in Consul.
        Return the service address and port.
        '''
        (index, val) = self.ch.catalog.service(service_name)
        if len(val) > 0:                # catalog.service returns an empty array if service not found
            service = val[0]            # Could be multiple listings, but we take the first
            if ('ServiceAddress' in service) and (len(service['ServiceAddress']) > 0):
                service_address = service['ServiceAddress']    # Most services should have this
            else:
                service_address = service['Address']         # "External" services will have this only
            service_port = service['ServicePort']
        else:
            raise Exception('Could not find service information for "{0}"'.format(service_name))

        return service_address, service_port

    def add_to_entry(self, key, add_name, add_value):
        '''
        Find 'key' in consul.
        Treat its value as a JSON string representing a dict.
        Extend the dict by adding an entry with key 'add_name' and value 'add_value'.
        Turn the resulting extended dict into a JSON string.
        Store the string back into Consul under 'key'.
        Watch out for conflicting concurrent updates.

        Example:
        Key 'xyz:dmaap' has the value '{"feed00": {"feed_url" : "http://example.com/feeds/999"}}'
        add_to_entry('xyz:dmaap', 'topic00', {'topic_url' : 'http://example.com/topics/1229'})
        should result in the value for key 'xyz:dmaap' in consul being updated to
        '{"feed00": {"feed_url" : "http://example.com/feeds/999"}, "topic00" : {"topic_url" : "http://example.com/topics/1229"}}'
        '''

        while True:     # do until update succeeds
            (index, val) = self.ch.kv.get(key)     # index gives version of key retrieved

            if val is None:     # no key yet
                vstring = '{}'
                mod_index = 0   # Use 0 as the cas index for initial insertion of the key
            else:
                vstring = val['Value']
                mod_index = val['ModifyIndex']

            # Build the updated dict
            # Exceptions just propagate
            v = json.loads(vstring)
            v[add_name] = add_value
            new_vstring = json.dumps(v)

            updated = self.ch.kv.put(key, new_vstring, cas=mod_index)       # if the key has changed since retrieval, this will return false
            if updated:
                break


    def delete_entry(self,entry_name):
        '''
        Delete an entire key-value entry whose key is 'entry_name' from the Consul KV store.

        Note that the kv.delete() operation always returns True,
        whether there's an entry with key 'entry_name' exists or not.  This doesn't seem like
        a great design, but it means it's safe to try to delete the same entry repeatedly.

        Note also in our application for this plugin, the uninstall workflow will always delete all of the topics and
        feeds we've stored into the 'component_name:dmaap' entry.

        Given the two foregoing notes, it is safe for this plugin to attempt to delete the entire
        'component_name:dmaap' entry any time it performs an 'unlink' operation for a publishes or
        subscribes relationship.   The first unlink will actually remove the entry, the subsequent ones
        will harmlessly try to remove it again.

        The 'correct' approach would be to have a delete_from_entry(self, key, delete_name) that fetches
        the entry from Consul, removes only the topic or feed being unlinked, and then puts the resulting
        entry back into Consul.  It would be very similar to add_from_entry.  When there's nothing left
        in the entry, then the entire entry would be deleted.
        '''
        self.ch.kv.delete(entry_name)
