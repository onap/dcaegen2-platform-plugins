# ============LICENSE_START==========================================
# ===================================================================
# Copyright (c) 2018 AT&T
# Copyright (c) 2020 Pantheon.tech. All rights reserved.
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#         http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.
# ============LICENSE_END============================================


from setuptools import setup

# Replace the place holders with values for your project

setup(

    # Do not use underscores in the plugin name.
    name='helm',
    version='4.1.0',
    author='Nicolas Hu(AT&T)',
    author_email='jh245g@att.com',
    description='This plugin will install/uninstall/upgrade/rollback helm '
                'charts of ONAP components. ',

    # This must correspond to the actual packages in the plugin.
    packages=['plugin'],

    license='LICENSE',
    zip_safe=False,
    install_requires=[
        'pyyaml>=3.12',
        # The package specified by requirements would be replaced with 5.0.5.1+
        # when this package is installed. That currently breaks on python3.
        #'cloudify-common>=5.0.5',
    ],
    test_requires=[
        'nose',
    ],
)
