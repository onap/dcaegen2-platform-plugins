# ============LICENSE_START=======================================================
# org.onap.dcae
# ================================================================================
# Copyright (c) 2018 AT&T Intellectual Property. All rights reserved.
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
#

import uuid
import json

MSB_ANNOTATION_KEY = 'msb.onap.org/service-info'

def _sanitize_service_info(service_info):
    '''
    Sanitize a dict containing the MSB annotation parameters for registering
    a service with MSB.  (Not bullet proof, but useful.)
    MSB registration happens asynchronously from the installation flow:  an MSB process
    watches the k8s event stream for new Service creations and looks for the MSB annotation.
    A bad annotation will fail silently.  This sanitization process should make sure that something
    gets put into    the MSB's list of services, so that the problem can be seen.

    service_info is a dict containing the MSB annotation parameters.
    -- serviceName: the name under which the service is to be registered (default: random--pretty useless!)
    -- port: the container port on which the service can be contacted (default: "80"--nearly as useless)
    -- version: the API version (default: "v1")
    -- url: the path to the application's API endpoint (default: "/")
    -- protocol: see the MSB documentation--the default is usually OK (default: "REST")
    -- enable_ssl: a flag indicating if the service uses SSL (True) or not (False) (default: True)
    -- visualRange: "1" means the service is exposed only in ONAP, "0" means externally (default: "1")
       (Note this is a string value)
    '''
    return {
        'serviceName': service_info.get('serviceName', str(uuid.uuid4())),
        'port': str(service_info.get('port', '80')),
        'version': service_info.get('version','v1'),
        'url': service_info.get('url','/'),
        'protocol': service_info.get('protocol','REST'),
        'enable_ssl': bool(service_info.get('enable_ssl', False)),
        'visualRange': str(service_info.get('visualRange', '1'))
    }

def create_msb_annotation(msb_service_list):
    '''
    Creates an annotation that can be added to a k8s Service to trigger
    registration with MSB.
    msb_list is a list of dicts each containing MSB registration information for a
    service.  (One k8s Service can have multiple ports, each one of which can be 
    registered as an MSB service.)
    '''
    return {MSB_ANNOTATION_KEY : json.dumps([_sanitize_service_info(service_info) for service_info in msb_service_list])}
