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
from ConfigParser import ConfigParser

import requests
from cloudify import ctx


class DiscoveryClient(object):
    """
    talking to consul either at
    url from the config file /opt/onap/config.txt on Cloudify Manager host
    or at http://consul:8500 or at http://localhost:8500.
    """
    CONFIG_PATH = "/opt/onap/config.txt"
    SERVICE_MASK = "http://{consul_host}/v1/catalog/service/{key}"
    KV_MASK = "http://{consul_host}/v1/kv/{key}"

    _lazy_inited = False
    _consul_hosts = None

    @staticmethod
    def _lazy_init():
        """find out where is consul - either from config file or hardcoded 'consul'"""
        if DiscoveryClient._lazy_inited:
            return
        DiscoveryClient._lazy_inited = True
        DiscoveryClient._consul_hosts = ["consul:8500", "localhost:8500"]

        try:
            config_parser = ConfigParser()
            if not config_parser.read(DiscoveryClient.CONFIG_PATH):
                ctx.logger.warn("not found config file at {config_path}"
                                .format(config_path=DiscoveryClient.CONFIG_PATH))
                return
            consul_host = config_parser.get('consul', 'address')
            if not consul_host:
                ctx.logger.warn("not found consul address in config file {config_path}"
                                .format(config_path=DiscoveryClient.CONFIG_PATH))
                return
            DiscoveryClient._consul_hosts.insert(0, consul_host)
            ctx.logger.info("got consul_host: {consul_host} from config file {config_path}"
                            .format(consul_host=DiscoveryClient._consul_hosts[0],
                                    config_path=DiscoveryClient.CONFIG_PATH))

        except Exception as ex:
            ctx.logger.warn("failed to get consul host from file {config_path}: {ex}"
                            .format(config_path=DiscoveryClient.CONFIG_PATH, ex=str(ex)))

    @staticmethod
    def _safe_get_url(url_mask, key):
        """safely http get to url"""
        for consul_host in DiscoveryClient._consul_hosts:
            try:
                url = url_mask.format(consul_host=consul_host, key=key)
                ctx.logger.info("get {0}".format(url))
                return url, requests.get(url)

            except requests.ConnectionError as ex:
                ctx.logger.warn("ConnectionError - failed to get {0}: {1}".format(url, str(ex)))
        return None, None

    @staticmethod
    def get_service_url(service_name):
        """find the service record in consul"""
        DiscoveryClient._lazy_init()

        url, response = DiscoveryClient._safe_get_url(DiscoveryClient.SERVICE_MASK, service_name)

        if not response:
            ctx.logger.error("failed to get service_url for {0}".format(service_name))
            return None

        ctx.logger.info("got {0} for service_url at {1} response: {2}"
                        .format(response.status_code, url, response.text))

        if response.status_code != requests.codes.ok:
            return None

        resp_json = response.json()
        if not resp_json:
            return None
        service = resp_json[0]
        return "http://{0}:{1}".format(service["ServiceAddress"], service["ServicePort"])


    @staticmethod
    def get_value(key):
        """get the value for the key from consul-kv"""
        DiscoveryClient._lazy_init()

        url, response = DiscoveryClient._safe_get_url(DiscoveryClient.KV_MASK, key)

        if not response:
            ctx.logger.error("failed to get kv for {0}".format(key))
            return None

        ctx.logger.info("got {0} for kv at {1} response: {2}"
                        .format(response.status_code, url, response.text))

        if response.status_code != requests.codes.ok:
            return None

        data = response.json()
        if not data:
            ctx.logger.error("failed to get kv for %s", key)
            return None
        value = base64.b64decode(data[0]["Value"]).decode("utf-8")
        ctx.logger.info("consul-kv key=%s value(%s) data=%s",
                        key, value, json.dumps(data))
        return json.loads(value)
