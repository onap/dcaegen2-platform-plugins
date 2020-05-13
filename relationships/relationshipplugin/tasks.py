# ============LICENSE_START=======================================================
# org.onap.dcae
# ================================================================================
# Copyright (c) 2017-2020 AT&T Intellectual Property. All rights reserved.
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

import json
from cloudify import ctx
from cloudify.decorators import operation
from cloudify.exceptions import NonRecoverableError
from relationshipplugin import discovery as dis
import requests


SERVICE_COMPONENT_NAME = "service_component_name"
SELECTED_CONTAINER_DESTINATION = "selected_container_destination"
CONSUL_HOST = "consul_host"

CONSUL_HOSTNAME = "localhost"


# Lifecycle interface calls for component_connect_to

# NOTE: ctx.source and ctx.target are RelationshipSubjectContext
# Order of operation of relationships is bit confusing. These operations are
# implemented for `target_interfaces`. By observation, the target node processed,
# then the source is created, the relationship is run then the source is started.
# http://getcloudify.org/guide/3.1/dsl-spec-relationships.html#relationship-interfaces

@operation
def add_relationship(**kwargs):
    """Adds target to the source relationship list"""
    try:
        conn = dis.create_kv_conn(CONSUL_HOSTNAME)

        source_name = ctx.source.instance.runtime_properties[SERVICE_COMPONENT_NAME]
        # The use case for using the target name override is for the platform
        # blueprint where the cdap broker needs to connect to a cdap cluster but
        # the cdap cluster does not not use the component plugins so the name is
        # not generated.
        # REVIEW: Re-review this
        target_name = kwargs["target_name_override"] \
            if "target_name_override" in kwargs \
            else ctx.target.instance.runtime_properties[SERVICE_COMPONENT_NAME]

        dis.store_relationship(conn, source_name, target_name)
        ctx.logger.info("Created relationship: {0} to {1}".format(source_name,
            target_name))
    except Exception as e:
        ctx.logger.error("Unexpected error while adding relationship: {0}"
                .format(str(e)))
        raise NonRecoverableError(e)

@operation
def remove_relationship(**kwargs):
    """Removes target from the source relationship list"""
    try:
        conn = dis.create_kv_conn(CONSUL_HOSTNAME)

        source_name = ctx.source.instance.runtime_properties[SERVICE_COMPONENT_NAME]
        dis.delete_relationship(conn, source_name)
        ctx.logger.info("Removed relationship: {0}".format(source_name))
    except Exception as e:
        ctx.logger.error("Unexpected error while removing relationship: {0}"
                .format(str(e)))
        raise NonRecoverableError(e)


# Lifecycle interface calls for component_contained_in

@operation
def forward_destination_info(**kwargs):
    try:
        selected_target = ctx.target.instance.runtime_properties[SERVICE_COMPONENT_NAME]
        ctx.source.instance.runtime_properties[SELECTED_CONTAINER_DESTINATION] = selected_target
        ctx.logger.info("Forwarding selected target: {0}".format(ctx.source.instance.id))
    except Exception as e:
        ctx.logger.error("Unexpected error while forwarding selected target: {0}"
                .format(str(e)))
        raise NonRecoverableError(e)

@operation
def registered_to(**kwargs):
    """
    Intended to be used in platform blueprints, but possible to be reused elsewhere
    """
    ctx.logger.info(str(kwargs))
    address = kwargs["address_to_register"]
    name = kwargs["name_to_register"]
    port = kwargs["port_to_register"]

    (consul_host, consul_port) = (CONSUL_HOSTNAME, 8500)
    #Storing in source because that's who is getting registered
    ctx.source.instance.runtime_properties[CONSUL_HOST] = "http://{0}:{1}".format(consul_host, consul_port)
    ctx.source.instance.runtime_properties["name_to_register"] = name #careful! delete does not have access to inputs

    try:
        response = requests.put(url = "{0}/v1/agent/service/register".format(ctx.source.instance.runtime_properties[CONSUL_HOST]),
                     json = {
                              "name" : name,
                              "Address" : address,
                              "Port" : int(port)
                            },
                     headers={'Content-Type': 'application/json'})
        response.raise_for_status() #bomb if not 2xx
    except Exception as e:
        ctx.logger.error("Error while registering: {0}".format(str(e)))
        raise NonRecoverableError(e)

@operation
def registered_to_delete(**kwargs):
    """
    The deletion/opposite of registered_to
    """
    requests.put(url = "{0}/v1/agent/service/deregister/{1}".format(ctx.source.instance.runtime_properties[CONSUL_HOST], ctx.source.instance.runtime_properties["name_to_register"]),
                 headers={'Content-Type': 'Content-Type: application/json'})
    #this is on delete so do not do any checking
