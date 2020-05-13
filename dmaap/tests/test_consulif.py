# ============LICENSE_START=======================================================
# org.onap.dcae
# ================================================================================
# Copyright (c) 2017-2018 AT&T Intellectual Property. All rights reserved.
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


import pytest
from cloudify.exceptions import NonRecoverableError
import os
from consulif.consulif import ConsulHandle


# No connections are actually made to this host
CONSUL_HOST = "consul"                      # Should always be a local consul agent on Cloudify Manager
#CONSUL_PORT = '8510'
CONSUL_PORT = '8500'
DBCL_KEY_NAME = "dmaap_dbcl_info"           # Consul key containing DMaaP data bus credentials
DBC_SERVICE_NAME= "dmaap_bus_controller"    # Name under which the DMaaP bus controller is registered


def test_get_config_service(mockconsul):
    err_msg = "Error getting ConsulHandle when configuring dmaap plugin: {0}"
    _ch = ConsulHandle("http://{0}:{1}".format(CONSUL_HOST, CONSUL_PORT), None, None, None)

    config = _ch.get_config(DBCL_KEY_NAME)

    DMAAP_USER = config['dmaap']['username']
    DMAAP_PASS = config['dmaap']['password']
    DMAAP_OWNER = config['dmaap']['owner']

    if 'protocol' in config['dmaap']:
        DMAAP_PROTOCOL = config['dmaap']['protocol']
    else:
        DMAAP_PROTOCOL = 'https'    # Default to https (service discovery should give us this but doesn't

    if 'path' in config['dmaap']:
        DMAAP_PATH = config['dmaap']['path']
    else:
        DMAAP_PATH = 'webapi'       # Should come from service discovery but Consul doesn't support it

    service_address, service_port = _ch.get_service(DBC_SERVICE_NAME)

    DMAAP_API_URL = '{0}://{1}:{2}/{3}'.format(DMAAP_PROTOCOL, service_address, service_port, DMAAP_PATH)


def test_add_entry(mockconsul):
    _ch = ConsulHandle("http://{0}:{1}".format(CONSUL_HOST, CONSUL_PORT), None, None, None)

    key = 'DMAAP_TEST'
    name = 'dmaap_test_name'
    value = 'dmaap_test_value'
    _ch.add_to_entry(key, name, value)

    name = "dmaap_test_name_2"
    value = 'dmaap_test_value_2'
    _ch.add_to_entry(key, name, value)

    _ch.delete_entry(key)
