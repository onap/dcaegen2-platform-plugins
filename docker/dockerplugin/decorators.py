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

import copy
from cloudify import ctx
from cloudify.exceptions import NonRecoverableError, RecoverableError
from dockering import utils as doc
from dockerplugin import discovery as dis
from dockerplugin.exceptions import DockerPluginDeploymentError, \
    DockerPluginDependencyNotReadyError


def monkeypatch_loggers(task_func):
    """Sets up the dependent loggers"""

    def wrapper(**kwargs):
        # Ouch! Monkeypatch loggers
        doc.logger = ctx.logger
        dis.logger = ctx.logger

        return task_func(**kwargs)

    return wrapper


def wrap_error_handling_start(task_start_func):
    """Wrap error handling for the start operations"""

    def wrapper(**kwargs):
        try:
            return task_start_func(**kwargs)
        except DockerPluginDependencyNotReadyError as e:
            # You are here because things we need like a working docker host is not
            # available yet so let Cloudify try again later.
            raise RecoverableError(e)
        except DockerPluginDeploymentError as e:
            # Container failed to come up in the allotted time. This is deemed
            # non-recoverable.
            raise NonRecoverableError(e)
        except Exception as e:
            ctx.logger.error("Unexpected error while starting container: {0}"
                    .format(str(e)))
            raise NonRecoverableError(e)

    return wrapper


def merge_inputs_for_start(task_start_func):
    """Merge all inputs for start operation into one dict"""

    def wrapper (**kwargs):
        start_inputs = copy.deepcopy(ctx.instance.runtime_properties)
        start_inputs.update(kwargs)

        # Apparently kwargs contains "ctx" which is cloudify.context.CloudifyContext
        # This has to be removed and not copied into runtime_properties else you get
        # JSON serialization errors.
        if "ctx" in start_inputs:
            del start_inputs["ctx"]

        return task_start_func(**start_inputs)

    return wrapper
