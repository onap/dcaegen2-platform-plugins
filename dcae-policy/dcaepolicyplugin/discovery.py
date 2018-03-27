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

from cloudify import ctx

# it is safe to assume that consul agent is at localhost:8500 along with cloudify manager
CONSUL_SERVICE_URL = "http://localhost:8500/v1/catalog/service/{0}"

def discover_service_url(service_name):
    """find the service record in consul"""
    service_url_url = CONSUL_SERVICE_URL.format(service_name)
    ctx.logger.info("getting service_url at {0}".format(service_url_url))

    response = requests.get(service_url_url)

    ctx.logger.info("got service_url at {0} status({1}) response: {2}"
                    .format(service_url_url, response.status_code, response.text))

    if response.status_code == requests.codes.ok:
        resp_json = response.json()
        if resp_json:
            service = resp_json[0]
            return "http://{0}:{1}".format(service["ServiceAddress"], service["ServicePort"])
