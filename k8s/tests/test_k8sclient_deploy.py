# ============LICENSE_START=======================================================
# org.onap.dcae
# ================================================================================
# Copyright (c) 2018-2020 AT&T Intellectual Property. All rights reserved.
# Copyright (c) 2020 Nokia. All rights reserved.
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

# Test k8sclient deployment functions
# Verify that for a given configuration and set of inputs, k8sclient generates the proper
# Kubernetes entities

import pytest
from common import do_deploy
from common import do_deploy_ext
from common import verify_external_cert

def test_deploy_full_tls(mockk8sapi):
    ''' Deploy component with a full TLS configuration, to act as a server '''

    dep, deployment_description = do_deploy({"use_tls": True, "cert_directory": "/path/to/container/cert/directory" })

    app_container = dep.spec.template.spec.containers[0]
    assert app_container.volume_mounts[2].mount_path == "/path/to/container/cert/directory"

def test_deploy_tls_off(mockk8sapi):
    ''' TLS client only, but with cert directory configured '''

    dep, deployment_description = do_deploy({"use_tls": False, "cert_directory": "/path/to/container/cert/directory" })

    app_container = dep.spec.template.spec.containers[0]
    assert app_container.volume_mounts[2].mount_path == "/path/to/container/cert/directory"

def test_deploy_no_tls_info(mockk8sapi):
    ''' TLS client only, but with cert directory configured '''

    dep, deployment_description = do_deploy()

    app_container = dep.spec.template.spec.containers[0]
    assert app_container.volume_mounts[2].mount_path == "/opt/dcae/cacert"

def test_deploy_external_cert(mockk8sapi):
    ''' Deploy component with external TLS configuration '''

    dep, deployment_description = do_deploy_ext({"external_cert_directory": "/path/to/container/cert/directory/",
                                                 "use_external_tls": True,
                                                 "cert_type": "P12",
                                                 "ca_name": "myname",
                                                 "external_certificate_parameters": {
                                                     "common_name": "mycommonname",
                                                     "sans": "mysans"}
                                                 })

    app_container = dep.spec.template.spec.containers[0]
    assert app_container.volume_mounts[2].mount_path == "/opt/dcae/cacert"

    # Make sure all of the external init container parameters are correct
    verify_external_cert(dep)
