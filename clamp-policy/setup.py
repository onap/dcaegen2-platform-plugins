# ================================================================================
# Copyright (c) 2019 Wipro Limited Intellectual Property. All rights reserved.
# Copyright (c) 2019 Pantheon.tech. All rights reserved.
# Copyright (c) 2020 AT&T Intellectual Property. All rights reserved.
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

"""package for clamppolicyplugin - getting policy model id from policy-engine through policy-handler"""

from setuptools import setup

setup(
    name='clamppolicyplugin',
    description='Cloudify plugin for clamp.nodes.policy node to retrieve the policy model id',
    version="1.1.1",
    author='Vignesh K',
    packages=['clamppolicyplugin'],
    install_requires=[
        'requests>=2.11.0',
        'cloudify-common>=5.0.0',
    ],
    keywords='clamp policy model cloudify plugin',
    classifiers=[
        'Development Status :: 4 - Beta',
        'Intended Audience :: Developers',
        'Programming Language :: Python :: 2.7'
    ]
)
