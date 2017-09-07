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

from functools import partial
import json
import logging
import uuid
import requests
import consul


logger = logging.getLogger("discovery")


class DiscoveryError(RuntimeError):
    pass

class DiscoveryConnectionError(RuntimeError):
    pass

class DiscoveryServiceNotFoundError(RuntimeError):
    pass

class DiscoveryKVEntryNotFoundError(RuntimeError):
    pass


def _wrap_consul_call(consul_func, *args, **kwargs):
    """Wrap Consul call to map errors"""
    try:
        return consul_func(*args, **kwargs)
    except requests.exceptions.ConnectionError as e:
        raise DiscoveryConnectionError(e)


def generate_service_component_name(service_component_type):
    """Generate service component id used to pass into the service component
    instance and used as the key to the service component configuration.

    Format:
    <service component id>_<service component type>
    """
    # Random generated
    # Copied from cdap plugin
    return "{0}_{1}".format(str(uuid.uuid4()).replace("-",""),
            service_component_type)


def create_kv_conn(host):
    """Create connection to key-value store

    Returns a Consul client to the specified Consul host"""
    try:
        [hostname, port] = host.split(":")
        return consul.Consul(host=hostname, port=int(port))
    except ValueError as e:
        return consul.Consul(host=host)

def push_service_component_config(kv_conn, service_component_name, config):
    config_string = config if isinstance(config, str) else json.dumps(config)
    kv_put_func = partial(_wrap_consul_call, kv_conn.kv.put)

    if kv_put_func(service_component_name, config_string):
        logger.info("Added config for {0}".format(service_component_name))
    else:
        raise DiscoveryError("Failed to push configuration")

def remove_service_component_config(kv_conn, service_component_name):
    kv_delete_func = partial(_wrap_consul_call, kv_conn.kv.delete)
    kv_delete_func(service_component_name)


def get_kv_value(kv_conn, key):
    """Get a key-value entry's value from Consul

    Raises DiscoveryKVEntryNotFoundError if entry not found
    """
    kv_get_func = partial(_wrap_consul_call, kv_conn.kv.get)
    (index, val) = kv_get_func(key)

    if val:
        return json.loads(val['Value']) # will raise ValueError if not JSON, let it propagate
    else:
        raise DiscoveryKVEntryNotFoundError("{0} kv entry not found".format(key))


def _create_rel_key(service_component_name):
    return "{0}:rel".format(service_component_name)

def store_relationship(kv_conn, source_name, target_name):
    # TODO: Rel entry may already exist in a one-to-many situation. Need to
    # support that.
    rel_key = _create_rel_key(source_name)
    rel_value = [target_name] if target_name else []

    kv_put_func = partial(_wrap_consul_call, kv_conn.kv.put)
    kv_put_func(rel_key, json.dumps(rel_value))
    logger.info("Added relationship for {0}".format(rel_key))

def delete_relationship(kv_conn, service_component_name):
    rel_key = _create_rel_key(service_component_name)
    kv_get_func = partial(_wrap_consul_call, kv_conn.kv.get)
    index, rels = kv_get_func(rel_key)

    if rels:
        rels = json.loads(rels["Value"].decode("utf-8"))
        kv_delete_func = partial(_wrap_consul_call, kv_conn.kv.delete)
        kv_delete_func(rel_key)
        return rels
    else:
        return []

def lookup_service(kv_conn, service_component_name):
    catalog_get_func = partial(_wrap_consul_call, kv_conn.catalog.service)
    index, results = catalog_get_func(service_component_name)

    if results:
        return results
    else:
        raise DiscoveryServiceNotFoundError("Failed to find: {0}".format(service_component_name))


# TODO: Note these functions have been (for the most part) shamelessly lifted from
# dcae-cli and should really be shared.

def _is_healthy_pure(get_health_func, instance):
    """Checks to see if a component instance is running healthy

    Pure function edition

    Args
    ----
    get_health_func: func(string) -> complex object
        Look at unittests in test_discovery to see examples
    instance: (string) fully qualified name of component instance

    Returns
    -------
    True if instance has been found and is healthy else False
    """
    index, resp = get_health_func(instance)

    if resp:
        def is_passing(instance):
            return all([check["Status"] == "passing" for check in instance["Checks"]])

        return any([is_passing(instance) for instance in resp])
    else:
        return False

def is_healthy(consul_host, instance):
    """Checks to see if a component instance is running healthy

    Impure function edition

    Args
    ----
    consul_host: (string) host string of Consul
    instance: (string) fully qualified name of component instance

    Returns
    -------
    True if instance has been found and is healthy else False
    """
    cons = create_kv_conn(consul_host)

    get_health_func = partial(_wrap_consul_call, cons.health.service)
    return _is_healthy_pure(get_health_func, instance)


def add_to_entry(conn, key, add_name, add_value):
    """
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
    """
    while True:     # do until update succeeds
        (index, val) = conn.kv.get(key)     # index gives version of key retrieved

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

        updated = conn.kv.put(key, new_vstring, cas=mod_index)       # if the key has changed since retrieval, this will return false
        if updated:
            return v


def _find_matching_services(services, name_search, tags):
    """Find matching services given search criteria"""
    def is_match(service):
        srv_name, srv_tags = service
        return name_search in srv_name and \
                all(map(lambda tag: tag in srv_tags, tags))

    return [ srv[0] for srv in services.items() if is_match(srv) ]

def search_services(conn, name_search, tags):
    """Search for services that match criteria

    Args:
    -----
    name_search: (string) Name to search for as a substring
    tags: (list) List of strings that are tags. A service must match **all** the
        tags in the list.

    Retruns:
    --------
    List of names of services that matched
    """
    # srvs is dict where key is service name and value is list of tags
    catalog_get_services_func = partial(_wrap_consul_call, conn.catalog.services)
    index, srvs = catalog_get_services_func()

    if srvs:
        matches = _find_matching_services(srvs, name_search, tags)

        if matches:
            return matches

        raise DiscoveryServiceNotFoundError(
                "No matches found: {0}, {1}".format(name_search, tags))
    else:
        raise DiscoveryServiceNotFoundError("No services found")
