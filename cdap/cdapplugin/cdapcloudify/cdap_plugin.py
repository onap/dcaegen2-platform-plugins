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
from onap_dcae_dcaepolicy_lib import Policies

import requests
from cloudify import ctx
from cloudify.decorators import operation
from cloudify.exceptions import NonRecoverableError
import time
import uuid
import re
from cdapcloudify import discovery
import json
import requests

# Property keys
SERVICE_COMPONENT_NAME = "service_component_name"
SELECTED_BROKER = "selected_broker"
PUB_C = "streams_publishes_for_config"
SUB_C = "streams_subscribes_for_config"
SER_C = "services_calls_for_config"
STREAMS_PUBLISHES  = "streams_publishes"
STREAMS_SUBSCRIBES = "streams_subscribes"
SERVICES_CALLS = "services_calls"

# Custom Exception
class BadConnections(NonRecoverableError):
    pass


def _trigger_update(updated_policies):
    """
    Helper function for reconfiguring after a policy update

    updated_policies is assumed to be a list of JSONs that are applicable to the brokers smart interface
    """
    for p in updated_policies:
        ctx.logger.info("Reconfiguring CDAP application via smart interface")
        return discovery.reconfigure_in_broker(
                   cdap_broker_name = ctx.instance.runtime_properties[SELECTED_BROKER],
                   service_component_name = ctx.instance.runtime_properties[SERVICE_COMPONENT_NAME],
                   config = p,
                   reconfiguration_type = "program-flowlet-smart",
                   logger = ctx.logger)

def _validate_conns(connections):
    """
    Cloudify allows you to type spec a data type in a type file, however it does not appear to do strict checking on blueprints against that.
    Sad!
    The "connections" block has an important structure to this plugin, so here we validate it and fail fast if it is not correct.
    """
    try:
        def _assert_ks_in_d(ks,d):
            for k in ks:
                assert(k in d)
        assert STREAMS_PUBLISHES in connections
        assert STREAMS_SUBSCRIBES in connections
        for s in connections[STREAMS_PUBLISHES] + connections[STREAMS_SUBSCRIBES]:
            _assert_ks_in_d(["name", "location", "type", "config_key"], s)
            assert(s["type"] in ["message_router", "data_router"])
            if s["type"] == "message_router":
                _assert_ks_in_d(["aaf_username", "aaf_password", "client_role"], s) #I am not checking that these are not blank. I will leave it possible for you to put empty values for these, but force you to acknowledge that you are doing so by not allowing these to be ommited.
            #nothing extra for DR; no AAF, no client role.
    except:
        raise BadConnections("Bad Connections definition in blueprint") #is a NoneRecoverable

def _streams_iterator(streams):
    """
    helper function for iterating over streams_publishes and subscribes
    note! this is an impure function. it also sets the properties the dmaap plugin needs into runtime properties
    """
    for_config = {}
    for s in streams:
        if s["type"] == "message_router":
            #set the properties the DMaaP plugin needs
            ctx.instance.runtime_properties[s["name"]] = {"client_role" : s["client_role"], "location" : s["location"]}
            #form (or append to) the dict the component will get, including the template for the CBS
            for_config[s["config_key"]] = {"aaf_username" : s["aaf_username"], "aaf_password" : s["aaf_password"], "type" : s["type"], "dmaap_info" : "<< " + s["name"] + ">>"} #will get bound by CBS
        if s["type"] == "data_router":
            #set the properties the DMaaP plugin needs$
            ctx.instance.runtime_properties[s["name"]] = {"location" : s["location"]}
            #form (or append to) the dict the component will get, including the template for the CBS$
            for_config[s["config_key"]] = {"type" : s["type"], "dmaap_info" : "<<" + s["name"] + ">>"} #will get bound by CBS

    return for_config

def _services_calls_iterator(services_calls):
    """
    helper function for iterating over services_calls
    """
    for_config = {}
    for s in services_calls:
        #form (or append to) the dict the component will get, including the template for the CBS
        for_config[s["config_key"]] = "{{ " + s["service_component_type"] + " }}" #will get bound by CBS
    return for_config

######################
# Decorators
######################
def try_raise_nonr(func):
    def inner(*args, **kwargs):
        try:
            return func(*args, **kwargs)
        except Exception as e:
            raise NonRecoverableError(e)
    return inner

######################
# Cloudify Operations
######################

@operation
@try_raise_nonr
def create(connected_broker_dns_name, **kwargs):
    """
    setup critical runtime properties
    """

    #fail fast
    _validate_conns(ctx.node.properties["connections"])

    #The config binding service needs to know whether cdap or docker. Currently (aug 1 2018) it looks for "cdap_app" in the name
    service_component_name = "{0}_cdap_app_{1}".format(str(uuid.uuid4()).replace("-",""), ctx.node.properties["service_component_type"])

    #set this into a runtime dictionary
    ctx.instance.runtime_properties[SERVICE_COMPONENT_NAME] = service_component_name

    #fetch the broker name from inputs and set it in runtime properties so other functions can use it
    ctx.instance.runtime_properties[SELECTED_BROKER] = connected_broker_dns_name

    #set the properties the DMaap plugin expects for message router
    #see the README for the structures of these keys
    #NOTE! This has to be done in create because Jack's DMaaP plugin expects to do it's thing in preconfigure.
    #      and we need to get this key into consul before start
    #set this as a runtime property for start to use
    ctx.instance.runtime_properties[PUB_C] = _streams_iterator(ctx.node.properties["connections"][STREAMS_PUBLISHES])
    ctx.instance.runtime_properties[SUB_C] = _streams_iterator(ctx.node.properties["connections"][STREAMS_SUBSCRIBES])
    ctx.instance.runtime_properties[SER_C] = _services_calls_iterator(ctx.node.properties["connections"][SERVICES_CALLS])

@operation
@try_raise_nonr
@Policies.gather_policies_to_node
def deploy_and_start_application(**kwargs):
    """
    pushes the application into the workspace and starts it
    """
    #parse TOSCA model params
    config_template = ctx.node.properties["app_config"]

    #there is a typed section in the node type called "connections", but the broker expects those two keys at the top level of app_config, so add them here
    #In cloudify you can't have a custom data type and then specify unknown propertys, the vlidation will fail, so typespeccing just part of app_config doesnt work
    #the rest of the CDAP app's app_config is app-dependent
    config_template[SERVICES_CALLS] = ctx.instance.runtime_properties[SER_C]
    config_template[STREAMS_PUBLISHES] = ctx.instance.runtime_properties[PUB_C]
    config_template[STREAMS_SUBSCRIBES] = ctx.instance.runtime_properties[SUB_C]

    #register with broker
    ctx.logger.info("Registering with Broker, config template was: {0}".format(json.dumps(config_template)))
    response = discovery.put_broker(
        cdap_broker_name = ctx.instance.runtime_properties[SELECTED_BROKER],
        service_component_name = ctx.instance.runtime_properties[SERVICE_COMPONENT_NAME],
        namespace = ctx.node.properties["namespace"],
        streamname = ctx.node.properties["streamname"],
        jar_url = ctx.node.properties["jar_url"],
        artifact_name = ctx.node.properties["artifact_name"],
        artifact_version = ctx.node.properties["artifact_version"],
        app_config = config_template,
        app_preferences = ctx.node.properties["app_preferences"],
        service_endpoints = ctx.node.properties["service_endpoints"],
        programs = ctx.node.properties["programs"],
        program_preferences = ctx.node.properties["program_preferences"],
        logger = ctx.logger)

    response.raise_for_status() #bomb if not 2xx

    #TODO! Would be better to do an initial merge first before deploying, but the merge is complicated for CDAP
    #because of app config vs. app preferences. So, for now, let the broker do the work with an immediate reconfigure
    #get policies that may have changed prior to this blueprint deployment
    policy_configs = Policies.get_policy_configs()
    if policy_configs is not None:
        ctx.logger.info("Updated policy configs: {0}".format(policy_configs))
        response = _trigger_update(policy_configs)
        response.raise_for_status() #bomb if not 2xx

@operation
def stop_and_undeploy_application(**kwargs):
    #per jack Lucas, do not raise Nonrecoverables on any delete operation. Keep going on them all, cleaning up as much as you can.
    #bombing would also bomb the deletion of the rest of the blueprint
    ctx.logger.info("Undeploying CDAP application")
    try: #deregister with the broker, which will also take down the service from consul
        response = discovery.delete_on_broker(
                                 cdap_broker_name = ctx.instance.runtime_properties[SELECTED_BROKER],
                                 service_component_name =  ctx.instance.runtime_properties[SERVICE_COMPONENT_NAME],
                                 logger = ctx.logger)
        response.raise_for_status() #bomb if not 2xx
    except Exception as e:
        ctx.logger.error("Error deregistering from Broker, but continuing with deletion process: {0}".format(e))

@operation
def delete_all_registered_apps(connected_broker_dns_name, **kwargs):
    """
    Used in the cdap broker deleter node.
    Deletes all registered applications (in the broker)
    per jack Lucas, do not raise Nonrecoverables on any delete operation. Keep going on them all, cleaning up as much as you can.
    """
    ctx.logger.info("Undeploying CDAP application")
    try:
        response = discovery.delete_all_registered_apps(
                       cdap_broker_name = connected_broker_dns_name,
                       logger = ctx.logger)
        response.raise_for_status() #bomb if not 2xx
    except Exception as e:
        ctx.logger.error("Error deregistering from Broker, but continuing with deletion process: {0}".format(e))

############
#RECONFIGURATION
#   These calls works as follows:
#        1) it expects "new_config_template" to be a key in kwargs, i.e., passed in using execute_operations -p parameter
#        2) it pushes the new unbound config down to the broker
#        3) broker deals with the rest
############
@operation
@try_raise_nonr
def app_config_reconfigure(new_config_template, **kwargs):
    """
    reconfigure the CDAP app's app config
    """
    ctx.logger.info("Reconfiguring CDAP application via app_config")
    response = discovery.reconfigure_in_broker(
                   cdap_broker_name = ctx.instance.runtime_properties[SELECTED_BROKER],
                   service_component_name = ctx.instance.runtime_properties[SERVICE_COMPONENT_NAME],
                   config = new_config_template, #This keyname will likely change per policy handler
                   reconfiguration_type = "program-flowlet-app-config",
                   logger = ctx.logger)
    response.raise_for_status() #bomb if not 2xx

@operation
@try_raise_nonr
def app_preferences_reconfigure(new_config_template, **kwargs):
    """
    reconfigure the CDAP app's app preferences
    """
    ctx.logger.info("Reconfiguring CDAP application via app_preferences")
    response = discovery.reconfigure_in_broker(
                   cdap_broker_name = ctx.instance.runtime_properties[SELECTED_BROKER],
                   service_component_name = ctx.instance.runtime_properties[SERVICE_COMPONENT_NAME],
                   config = new_config_template, #This keyname will likely change per policy handler
                   reconfiguration_type = "program-flowlet-app-preferences",
                   logger = ctx.logger)
    response.raise_for_status() #bomb if not 2xx

@operation
@try_raise_nonr
def app_smart_reconfigure(new_config_template, **kwargs):
    """
    reconfigure the CDAP app via the broker smart interface
    """
    ctx.logger.info("Reconfiguring CDAP application via smart interface")
    response = _trigger_update([new_config_template])
    response.raise_for_status() #bomb if not 2xx

@operation
@try_raise_nonr
@Policies.update_policies_on_node(configs_only=True)
def policy_update(updated_policies,  **kwargs):
    #its already develiered through policy
    ctx.logger.info("Policy update recieved. updated policies: {0}".format(updated_policies))
    #TODO! In the future, if we really have many different policies, would be more efficient to do a single merge here.
    #However all use cases today are a single policy so OK with this for loop for now.
    response = _trigger_update(updated_policies)
    response.raise_for_status() #bomb if not 2xx

