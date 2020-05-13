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

from cloudify.decorators import workflow
from cloudify.workflows import ctx
from cloudify.exceptions import NonRecoverableError
import json
import yaml
import base64


@workflow
def upgrade(node_instance_id, config_set, config, config_url, config_format,
            chart_version, chart_repo_url, repo_user, repo_user_password, **kwargs):
    node_instance = ctx.get_node_instance(node_instance_id)

    if not node_instance_id:
        raise NonRecoverableError(
            'No such node_instance_id in deployment: {0}.'.format(
                node_instance_id))

    kwargs = {}
    kwargs['config'] = ''
    kwargs['chart_version'] = str(chart_version)
    kwargs['chart_repo'] = str(chart_repo_url)
    kwargs['config_set'] = str(config_set)
    kwargs['config_json'] = str(config)
    kwargs['config_url'] = str(config_url)
    kwargs['config_format'] = str(config_format)
    kwargs['repo_user'] = str(repo_user)
    kwargs['repo_user_passwd'] = str(repo_user_password)
    operation_args = {'operation': 'upgrade', }
    operation_args['kwargs'] = kwargs
    node_instance.execute_operation(**operation_args)


@workflow
def rollback(node_instance_id, revision, **kwargs):
    node_instance = ctx.get_node_instance(node_instance_id)

    if not node_instance_id:
        raise NonRecoverableError(
            'No such node_instance_id in deployment: {0}.'.format(
                node_instance_id))

    kwargs = {}
    kwargs['revision'] = str(revision)
    operation_args = {'operation': 'rollback', }
    operation_args['kwargs'] = kwargs
    node_instance.execute_operation(**operation_args)

@workflow
def status(**kwargs):

    for node in ctx.nodes:
        for node_instance in node.instances:
            kwargs = {}
            operation_args = {'operation': 'status', }
            operation_args['kwargs'] = kwargs
            node_instance.execute_operation(**operation_args)
