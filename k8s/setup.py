# ============LICENSE_START=======================================================
# org.onap.dcae
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

from setuptools import setup

setup(
    name='k8splugin',
    description='Cloudify plugin for containerized components deployed using Kubernetes',
    version="1.4.5",
    author='J. F. Lucas, Michael Hwang, Tommy Carpenter',
    packages=['k8splugin','k8sclient','msb','configure'],
    zip_safe=False,
    install_requires=[
        "python-consul>=0.6.0,<1.0.0",
        "uuid==1.30",
        "onap-dcae-dcaepolicy-lib>=2.4.1,<3.0.0",
        "cloudify-plugins-common==3.4",
        "cloudify-python-importer==0.1.0",
        "kubernetes==4.0.0"
    ]
)
