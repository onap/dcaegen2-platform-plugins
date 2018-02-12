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

"""client to talk to consul on standard port 8500"""

import requests

# it is safe to assume that consul agent is at localhost:8500 along with cloudify manager
CONSUL_SERVICE_URL = "http://localhost:8500/v1/catalog/service/{0}"

def discover_service_url(service_name):
    """find the service record in consul"""
    response = requests.get(CONSUL_SERVICE_URL.format(service_name))
    response.raise_for_status()
    resp_json = response.json()
    if resp_json:
        service = resp_json[0]
        return "http://{0}:{1}".format(service["ServiceAddress"], service["ServicePort"])
