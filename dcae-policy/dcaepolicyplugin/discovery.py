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

import base64
import json

import requests
from cloudify import ctx
from cloudify.exceptions import NonRecoverableError

# it is safe to assume that consul agent is at consul:8500
# define consul alis in /etc/hosts on cloudify manager vm
# $ cat /etc/hosts
# 127.0.0.1   localhost localhost.localdomain localhost4 localhost4.localdomain4 consul

CONSUL_SERVICE_URL = "http://consul:8500/v1/catalog/service/{0}"
CONSUL_KV_MASK = "http://consul:8500/v1/kv/{0}"


def discover_service_url(service_name):
    """find the service record in consul"""
    service_url = CONSUL_SERVICE_URL.format(service_name)
    ctx.logger.info("getting service_url at {0}".format(service_url))

    try:
        response = requests.get(service_url, timeout=60)
    except requests.ConnectionError as ex:
        raise NonRecoverableError(
            "ConnectionError - failed to get {0}: {1}".format(service_url, str(ex)))

    ctx.logger.info("got {0} for service_url at {1} response: {2}"
                    .format(response.status_code, service_url, response.text))

    if response.status_code != requests.codes.ok:
        return

    resp_json = response.json()
    if resp_json:
        service = resp_json[0]
        return "http://{0}:{1}".format(service["ServiceAddress"], service["ServicePort"])


def discover_value(key):
    """get the value for the key from consul-kv"""
    kv_url = CONSUL_KV_MASK.format(key)
    ctx.logger.info("getting kv at {0}".format(kv_url))

    try:
        response = requests.get(kv_url, timeout=60)
    except requests.ConnectionError as ex:
        raise NonRecoverableError(
            "ConnectionError - failed to get {0}: {1}".format(kv_url, str(ex)))

    ctx.logger.info("got {0} for kv at {1} response: {2}"
                    .format(response.status_code, kv_url, response.text))

    if response.status_code != requests.codes.ok:
        return

    data = response.json()
    if not data:
        ctx.logger.error("failed discover_value %s", key)
        return
    value = base64.b64decode(data[0]["Value"]).decode("utf-8")
    ctx.logger.info("consul-kv key=%s value(%s) data=%s",
                    key, value, json.dumps(data))
    return json.loads(value)
