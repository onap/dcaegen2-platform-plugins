# ================================================================================
# Copyright (c) 2019 Wipro Limited Intellectual Property. All rights reserved.
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

"""tasks are the cloudify operations invoked on interfaces defined in the blueprint"""

from cloudify import ctx
from cloudify.decorators import operation
from cloudify.exceptions import NonRecoverableError

CLAMP_POLICY_TYPE = 'clamp.nodes.policy'

@operation
def policy_get(**kwargs):
    """clamppolicyplugin - Dummy Function returning no value"""
    ctx.logger.info("clamppolicyplugin - Inside policy_get dummy function")
