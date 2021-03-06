# ============LICENSE_START=======================================================
# org.onap.dcae
# ================================================================================
# Copyright (c) 2017-2020 AT&T Intellectual Property. All rights reserved.
# Copyright (c) 2020 Pantheon.tech. All rights reserved.
# Copyright (c) 2020-2021 Nokia. All rights reserved.
# Copyright (c) 2020 J. F. Lucas.  All rights reserved.
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

from setuptools import setup

setup(
    name='k8splugin',
    description='Cloudify plugin for containerized components deployed using Kubernetes',
    version="3.9.0",
    author='J. F. Lucas, Michael Hwang, Tommy Carpenter, Joanna Jeremicz, Sylwia Jakubek, Jan Malkiewicz, Remigiusz Janeczek, Piotr Marcinkiewicz, Tomasz Wrobel',
    packages=['k8splugin','k8sclient','configure'],
    zip_safe=False,
    install_requires=[
        'python-consul>=0.6.0',
        'onap-dcae-dcaepolicy-lib>=2.5.1',
        'kubernetes==12.0.1',
        'cloudify-common>=5.0.0',
        'validators>=0.14.2',
        'fqdn==1.5.0',
        'uritools>=2.2.0',
    ]
)
