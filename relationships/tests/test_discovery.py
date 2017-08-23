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

import pytest
from relationshipplugin import discovery as dis


def test_create_kv_conn_parse_host():
    # Just hostname
    hostname = "some-consul.far.away"
    assert (hostname, 8500) == dis._parse_host(hostname)

    # Hostname:port
    port = 8080
    host = "{0}:{1}".format(hostname, port)
    assert (hostname, port) == dis._parse_host(host)

    # Invalid port
    port = "abc"
    host = "{0}:{1}".format(hostname, port)
    with pytest.raises(dis.DiscoveryError):
        dis._parse_host(host)

    # Hanging colon
    port = ""
    host = "{0}:{1}".format(hostname, port)
    assert (hostname, 8500) == dis._parse_host(host)
