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

from urlparse import urlparse
import json
import consul


class DiscoveryError(RuntimeError):
    pass

def _create_rel_key(service_component_name):
    return "{0}:rel".format(service_component_name)

def _parse_host(host):
    """Parse host string

    Returns:
        Tuple of the hostname and port to use to connect to Consul
    """
    def parse_urlparse_result(pr):
        if not pr.hostname:
            raise DiscoveryError("Invalid Consul host provided: {0}".format(host))

        try:
            # Port 8500 is the Consul default
            return (pr.hostname, pr.port if pr.port else 8500)
        except ValueError as e:
            # Something bad happened with port
            raise DiscoveryError("Invalid Consul host provided: {0}".format(host))

    pr = urlparse(host)

    # urlparse requires scheme to be set in order to be useful
    if pr.scheme and pr.netloc:
        return parse_urlparse_result(pr)
    else:
        return parse_urlparse_result(urlparse("http://{0}".format(host)))


def create_kv_conn(host):
    """Create connection to key-value store

    Returns a Consul client to the specified Consul host
    """
    (hostname, port) = _parse_host(host)
    return consul.Consul(host=hostname, port=port)

def store_relationship(kv_conn, source_name, target_name):
    # TODO: Rel entry may already exist in a one-to-many situation. Need to
    # support that.
    rel_key = _create_rel_key(source_name)
    rel_value = [target_name] if target_name else []

    kv_conn.kv.put(rel_key, json.dumps(rel_value))
    print("Added relationship for {0}".format(rel_key))

def delete_relationship(kv_conn, service_component_name):
    rel_key = _create_rel_key(service_component_name)
    index, rels = kv_conn.kv.get(rel_key)

    if rels:
        rels = json.loads(rels["Value"].decode("utf-8"))
        kv_conn.kv.delete(rel_key)
        return rels
    else:
        return []
