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

import pytest

@pytest.fixture()
def mockconfig(monkeypatch):
    from configure import configure
    """ Override the regular configure() routine that reads a file and calls Consul"""
    def altconfig():
      config = configure._set_defaults()
      config["consul_host"] = config["consul_dns_name"]
      return config
    monkeypatch.setattr(configure, 'configure', altconfig)

@pytest.fixture()
def mockk8sapi(monkeypatch):
    import k8sclient.k8sclient
    from kubernetes import client

    # We need to patch the kubernetes 'client' module
    # Awkward because of the way it requires a function call
    # to get an API object
    core = client.CoreV1Api()
    ext = client.ExtensionsV1beta1Api()

    def pseudo_deploy(namespace, dep):
        return dep

    def pseudo_service(namespace, svc):
        return svc

    # patched_core returns a CoreV1Api object with the
    # create_namespaced_service method stubbed out so that there
    # is no attempt to call the k8s API server
    def patched_core():
        monkeypatch.setattr(core, "create_namespaced_service", pseudo_service)
        return core

    # patched_ext returns an ExtensionsV1beta1Api object with the
    # create_namespaced_deployment method stubbed out so that there
    # is no attempt to call the k8s API server
    def patched_ext():
        monkeypatch.setattr(ext,"create_namespaced_deployment", pseudo_deploy)
        return ext

    def pseudo_configure(loc):
        pass

    monkeypatch.setattr(k8sclient.k8sclient,"_configure_api", pseudo_configure)
    monkeypatch.setattr(client, "CoreV1Api", patched_core)
    monkeypatch.setattr(client,"ExtensionsV1beta1Api", patched_ext)