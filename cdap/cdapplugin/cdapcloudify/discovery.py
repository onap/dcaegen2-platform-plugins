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

import requests
import json

CONSUL_HOST = "http://localhost:8500"

def _get_broker_url(cdap_broker_name, service_component_name, logger):
    """
    fetch the broker connection information from Consul
    """
    def _get_connection_info_from_consul(service_component_name, logger):
        """
        Call consul's catalog
        TODO: currently assumes there is only one service
        """
        url = "{0}/v1/catalog/service/{1}".format(CONSUL_HOST, service_component_name)
        logger.info("Trying to query: {0}".format(url))
        res = requests.get(url)
        res.raise_for_status()
        services = res.json()
        return services[0]["ServiceAddress"], services[0]["ServicePort"]

    broker_ip, broker_port = _get_connection_info_from_consul(cdap_broker_name, logger)
    broker_url = "http://{ip}:{port}/application/{appname}".format(ip=broker_ip, port=broker_port, appname=service_component_name)
    logger.info("Trying to connect to broker endpoint: {0}".format(broker_url))
    return broker_url

"""
public
"""
def put_broker(cdap_broker_name, 
               service_component_name, 
               namespace, 
               streamname, 
               jar_url,
               artifact_name, 
               artifact_version,
               app_config,
               app_preferences, 
               service_endpoints, 
               programs, 
               program_preferences, 
               logger):
    """
    Conforms to Broker API 4.X
    """

    data = dict()
    data["cdap_application_type"] = "program-flowlet"
    data["namespace"] = namespace
    data["streamname"] = streamname
    data["jar_url"] = jar_url
    data["artifact_name"] = artifact_name
    data["artifact_version"] = artifact_version
    data["app_config"] = app_config
    data["app_preferences"] = app_preferences
    data["services"] = service_endpoints
    data["programs"] = programs
    data["program_preferences"] = program_preferences
    
    #register with the broker
    response = requests.put(_get_broker_url(cdap_broker_name, service_component_name, logger),
                            json = data, 
                            headers = {'content-type':'application/json'})
    logger.info((response, response.status_code, response.text))
    response.raise_for_status() #bomb if not 2xx

def reconfigure_in_broker(cdap_broker_name, 
                          service_component_name, 
                          config,
                          reconfiguration_type,
                          logger):
    #trigger a reconfiguration with the broker
    #man am I glad I broke the broker API from 3 to 4 to standardize this interface because now I only need one function here
    response = requests.put("{u}/reconfigure".format(u = _get_broker_url(cdap_broker_name, service_component_name, logger)),
                            headers = {'content-type':'application/json'},
                            json = {"reconfiguration_type" : reconfiguration_type, 
                                    "config" : config})
    logger.info((response, response.status_code, response.text))
    response.raise_for_status() #bomb if not 2xx

def delete_on_broker(cdap_broker_name, service_component_name, logger):
    #deregister with the broker
    response = requests.delete(_get_broker_url(cdap_broker_name, service_component_name, logger))
    logger.info((response, response.status_code, response.text))
    response.raise_for_status() #bomb if not 2xx

