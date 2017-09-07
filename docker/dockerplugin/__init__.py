# ============LICENSE_START=======================================================
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

# REVIEW: Tried to source the version from here but you run into import issues
# because "tasks" module is loaded. This method seems to be the PEP 396
# recommended way and is listed #3 here https://packaging.python.org/single_source_version/
# __version__ = '0.1.0'

from .tasks import create_for_components, create_for_components_with_streams, \
        create_and_start_container_for_components_with_streams, \
        create_for_platforms, create_and_start_container, \
        create_and_start_container_for_components, create_and_start_container_for_platforms, \
        stop_and_remove_container, cleanup_discovery, select_docker_host, unselect_docker_host, \
        policy_update
