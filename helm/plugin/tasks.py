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

import shutil
import errno
import sys
import pwd
import grp
import os
import re
import getpass
import subprocess
import json
import base64
import yaml
try:
    from urllib.request import Request, urlopen
except ImportError:
    from urllib2 import Request, urlopen

from cloudify import ctx
from cloudify import exceptions
from cloudify.decorators import operation
from cloudify.exceptions import OperationRetry
from cloudify.exceptions import NonRecoverableError
from cloudify_rest_client.exceptions import CloudifyClientError


def debug_log_mask_credentials(_command_str):
    debug_str = _command_str
    if _command_str.find("@") != -1:
        head, end = _command_str.rsplit('@', 1)
        proto, auth = head.rsplit('//', 1)
        uname, passwd = auth.rsplit(':', 1)
        debug_str = _command_str.replace(passwd, "************")
    ctx.logger.debug('command {0}.'.format(debug_str))

def execute_command(_command):
    debug_log_mask_credentials(_command)

    subprocess_args = {
        'args': _command.split(),
        'stdout': subprocess.PIPE,
        'stderr': subprocess.PIPE
    }

    debug_log_mask_credentials(str(subprocess_args))
    try:
        process = subprocess.Popen(**subprocess_args)
        output, error = process.communicate()
    except Exception as e:
        ctx.logger.debug(str(e))
        return False

    debug_log_mask_credentials(_command)
    ctx.logger.debug('output: {0} '.format(output))
    ctx.logger.debug('error: {0} '.format(error))
    ctx.logger.debug('process.returncode: {0} '.format(process.returncode))

    if process.returncode:
        ctx.logger.error('Error was returned while running helm command')
        return False

    return output


def configure_admin_conf():
    # Add the kubeadmin config to environment
    agent_user = getpass.getuser()
    uid = pwd.getpwnam(agent_user).pw_uid
    gid = grp.getgrnam('docker').gr_gid
    admin_file_dest = os.path.join(os.path.expanduser('~'), 'admin.conf')

    execute_command(
        'sudo cp {0} {1}'.format('/etc/kubernetes/admin.conf',
                                 admin_file_dest))
    execute_command('sudo chown {0}:{1} {2}'.format(uid, gid, admin_file_dest))

    with open(os.path.join(os.path.expanduser('~'), '.bashrc'),
              'a') as outfile:
        outfile.write('export KUBECONFIG=$HOME/admin.conf')
    os.environ['KUBECONFIG'] = admin_file_dest


def get_current_helm_value(chart_name):
    tiller_host = str(ctx.node.properties['tiller_ip']) + ':' + str(
        ctx.node.properties['tiller_port'])
    config_dir_root = str(ctx.node.properties['config_dir'])
    config_dir = config_dir_root + str(ctx.deployment.id) + '/'
    if str_to_bool(ctx.node.properties['tls_enable']):
        getValueCommand = subprocess.Popen(
            ["helm", "get", "values", "-a", chart_name, '--host', tiller_host,
             '--tls', '--tls-ca-cert', config_dir + 'ca.cert.pem',
             '--tls-cert',
             config_dir + 'helm.cert.pem', '--tls-key',
             config_dir + 'helm.key.pem'], stdout=subprocess.PIPE)
    else:
        getValueCommand = subprocess.Popen(
            ["helm", "get", "values", "-a", chart_name, '--host', tiller_host],
            stdout=subprocess.PIPE)
    value = getValueCommand.communicate()[0]
    valueMap = {}
    valueMap = yaml.safe_load(value)
    ctx.instance.runtime_properties['current-helm-value'] = valueMap


def get_helm_history(chart_name):
    tiller_host = str(ctx.node.properties['tiller_ip']) + ':' + str(
        ctx.node.properties['tiller_port'])
    config_dir_root = str(ctx.node.properties['config_dir'])
    config_dir = config_dir_root + str(ctx.deployment.id) + '/'
    if str_to_bool(ctx.node.properties['tls_enable']):
        getHistoryCommand = subprocess.Popen(
            ["helm", "history", chart_name, '--host', tiller_host, '--tls',
             '--tls-ca-cert', config_dir + 'ca.cert.pem', '--tls-cert',
             config_dir + 'helm.cert.pem', '--tls-key',
             config_dir + 'helm.key.pem'], stdout=subprocess.PIPE)
    else:
        getHistoryCommand = subprocess.Popen(
            ["helm", "history", chart_name, '--host', tiller_host],
            stdout=subprocess.PIPE)
    history = getHistoryCommand.communicate()[0]
    history_start_output = [line.strip() for line in history.split('\n') if
                            line.strip()]
    for index in range(len(history_start_output)):
        history_start_output[index] = history_start_output[index].replace('\t',
                                                                          ' ')
    ctx.instance.runtime_properties['helm-history'] = history_start_output


def tls():
    if str_to_bool(ctx.node.properties['tls_enable']):
        config_dir_root = str(ctx.node.properties['config_dir'])
        config_dir = config_dir_root + str(ctx.deployment.id) + '/'
        tls_command = ' --tls --tls-ca-cert ' + config_dir + 'ca.cert.pem ' \
                                                             '--tls-cert ' + \
                      config_dir + 'helm.cert.pem --tls-key ' + config_dir + \
                      'helm.key.pem '
        ctx.logger.debug(tls_command)
        return tls_command
    else:
        return ''


def tiller_host():
    tiller_host = ' --host ' + str(
        ctx.node.properties['tiller_ip']) + ':' + str(
        ctx.node.properties['tiller_port']) + ' '
    ctx.logger.debug(tiller_host)
    return tiller_host


def str_to_bool(s):
    s = str(s)
    if s == 'True' or s == 'true':
        return True
    elif s == 'False' or s == 'false':
        return False
    else:
        raise ValueError('Require [Tt]rue or [Ff]alse; got: {0}'.format(s))


def get_config_json(config_json, config_path, config_opt_f, config_file_nm):
    config_obj = {}
    config_obj = json.loads(config_json)
    config_file = config_path + config_file_nm + ".yaml"
    gen_config_file(config_file, config_obj)
    config_opt_f = config_opt_f + " -f " + config_file
    return config_opt_f


def pop_config_info(url, config_file, f_format, repo_user, repo_user_passwd):
    if url.find("@") != -1:
        head, end = url.rsplit('@', 1)
        head, auth = head.rsplit('//', 1)
        url = head + '//' + end
        username, password = auth.rsplit(':', 1)
        request = Request(url)
        base64string = base64.encodestring(
            '%s:%s' % (username, password)).replace('\n', '')
        request.add_header("Authorization", "Basic %s" % base64string)
        response = urlopen(request)
    elif repo_user != '' and repo_user_passwd != '':
        request = Request(url)
        base64string = base64.b64encode('%s:%s' % (repo_user, repo_user_passwd))
        request.add_header("Authorization", "Basic %s" % base64string)
        response = urlopen(request)
    else:
        response = urlopen(url)

    config_obj = {}
    if f_format == 'json':
        config_obj = json.load(response)
    elif f_format == 'yaml':
        config_obj = yaml.load(response)
    else:
        raise NonRecoverableError("Unable to get config input format.")

    gen_config_file(config_file, config_obj)


def gen_config_file(config_file, config_obj):
    try:
        with open(config_file, 'w') as outfile:
            yaml.safe_dump(config_obj, outfile, default_flow_style=False)
    except OSError as e:
        if e.errno != errno.EEXIST:
            raise


def gen_config_str(config_file, config_opt_f):
    try:
        with open(config_file, 'w') as outfile:
            yaml.safe_dump(config_opt_f, outfile, default_flow_style=False)
    except OSError as e:
        if e.errno != errno.EEXIST:
            raise


def get_rem_config(config_url, config_input_format, config_path, config_opt_f, config_file_nm, repo_user, repo_user_passwd):
    ctx.logger.debug("config_url=" + config_url)
    f_cnt = 0
    # urls = config_url.split()
    urls = [x.strip() for x in config_url.split(',')]
    if len(urls) > 1:
        for url in urls:
            f_cnt = f_cnt + 1
            config_file = config_path + config_file_nm + str(f_cnt) + ".yaml"
            pop_config_info(url, config_file, config_input_format, repo_user, repo_user_passwd)
            config_opt_f = config_opt_f + " -f " + config_file
    else:
        config_file = config_path + config_file_nm + ".yaml"
        pop_config_info(config_url, config_file, config_input_format, repo_user, repo_user_passwd)
        config_opt_f = config_opt_f + " -f " + config_file

    return config_opt_f


def get_config_str(config_file):
    if os.path.isfile(config_file):
        with open(config_file, 'r') as config_f:
            return config_f.read().replace('\n', '')
    return ''


def opt(config_file):
    opt_str = get_config_str(config_file)
    if opt_str != '':
        return opt_str.replace("'", "")
    return opt_str

def repo(repo_url, repo_user, repo_user_passwd):
    if repo_user != '' and repo_user_passwd != '' and repo_url.find("@") == -1:
        proto, ip = repo_url.rsplit('//', 1)
        return proto + '//' + repo_user + ':' + repo_user_passwd + '@' + ip
    else:
        return repo_url


@operation
def config(**kwargs):
    # create helm value file on K8s master
    configJson = str(ctx.node.properties['config'])
    configUrl = str(ctx.node.properties['config_url'])
    configUrlInputFormat = str(ctx.node.properties['config_format'])
    runtime_config = str(ctx.node.properties['runtime_config'])  # json
    componentName = ctx.node.properties['component_name']
    config_dir_root = str(ctx.node.properties['config_dir'])
    stable_repo_url = str(ctx.node.properties['stable_repo_url'])
    config_opt_set = str(ctx.node.properties['config_set'])
    repo_user = str(ctx.node.properties['repo_user'])
    repo_user_passwd = str(ctx.node.properties['repo_user_password'])
    ctx.logger.debug("debug " + configJson + runtime_config)
    # load input config
    config_dir = config_dir_root + str(ctx.deployment.id)

    if not os.path.exists(config_dir):
        try:
            os.makedirs(config_dir)
        except OSError as e:
            if e.errno != errno.EEXIST:
                raise

    ctx.logger.debug('tls-enable type ' + str(
        type(str_to_bool(ctx.node.properties['tls_enable']))))

    # create TLS cert files
    if str_to_bool(ctx.node.properties['tls_enable']):
        ctx.logger.debug('tls enable')
        ca_value = ctx.node.properties['ca']
        cert_value = ctx.node.properties['cert']
        key_value = ctx.node.properties['key']
        ca = open(config_dir + '/ca.cert.pem', "w+")
        ca.write(ca_value)
        ca.close()
        cert = open(config_dir + '/helm.cert.pem', "w+")
        cert.write(cert_value)
        cert.close()
        key = open(config_dir + '/helm.key.pem', "w+")
        key.write(key_value)
        key.close()
    else:
        ctx.logger.debug('tls disable')

    config_path = config_dir + '/' + componentName + '/'
    ctx.logger.debug(config_path)

    if os.path.exists(config_path):
        shutil.rmtree(config_path)

    try:
        os.makedirs(config_path)
    except OSError as e:
        if e.errno != errno.EEXIST:
            raise

    config_opt_f = ""
    if configJson == '' and configUrl == '':
        ctx.logger.debug("Will use default HELM value")
    elif configJson == '' and configUrl != '':
        config_opt_f = get_rem_config(configUrl, configUrlInputFormat, config_path, config_opt_f, "rc", repo_user, repo_user_passwd)
    elif configJson != '' and configUrl == '':
        config_opt_f = get_config_json(configJson, config_path, config_opt_f, "lc")
    else:
        raise NonRecoverableError("Unable to get config input")

    ctx.logger.debug("debug check runtime config")
    if runtime_config == '':
        ctx.logger.debug("there is no runtime config value")
    else:
        config_opt_f = get_config_json(runtime_config, config_path, config_opt_f, "rt")

    if configUrl != '' or configJson != '' or runtime_config != '':
        config_file = config_path + ".config_file"
        gen_config_str(config_file, config_opt_f)

    if config_opt_set != '':
        config_file = config_path + ".config_set"
        config_opt_set = " --set " + config_opt_set
        gen_config_str(config_file, config_opt_set)

    output = execute_command(
        'helm init --client-only --stable-repo-url ' + repo(stable_repo_url, repo_user, repo_user_passwd))
    if output == False:
        raise NonRecoverableError("helm init failed")


@operation
def start(**kwargs):
    # install the ONAP Helm chart
    # get properties from node
    repo_user = str(ctx.node.properties['repo_user'])
    repo_user_passwd = str(ctx.node.properties['repo_user_password'])
    chartRepo = ctx.node.properties['chart_repo_url']
    componentName = ctx.node.properties['component_name']
    chartVersion = str(ctx.node.properties['chart_version'])
    config_dir_root = str(ctx.node.properties['config_dir'])
    namespace = ctx.node.properties['namespace']

    config_path = config_dir_root + str(
        ctx.deployment.id) + '/' + componentName + '/'
    chart = chartRepo + "/" + componentName + "-" + str(chartVersion) + ".tgz"
    chartName = namespace + "-" + componentName
    config_file = config_path + ".config_file"
    config_set = config_path + ".config_set"
    installCommand = 'helm install ' + repo(chart, repo_user, repo_user_passwd) + ' --name ' + chartName + \
                     ' --namespace ' + namespace + opt(config_file) + \
                     opt(config_set) + tiller_host() + tls()

    output = execute_command(installCommand)
    if output == False:
        return ctx.operation.retry(
            message='helm install failed, re-try after 5 second ',
            retry_after=5)

    get_current_helm_value(chartName)
    get_helm_history(chartName)


@operation
def stop(**kwargs):
    # delete the ONAP helm chart
    # configure_admin_conf()
    # get properties from node
    namespace = ctx.node.properties['namespace']
    component = ctx.node.properties['component_name']
    chartName = namespace + "-" + component
    config_dir_root = str(ctx.node.properties['config_dir'])
    # Delete helm chart
    command = 'helm delete --purge ' + chartName + tiller_host() + tls()
    output = execute_command(command)
    if output == False:
        raise NonRecoverableError("helm delete failed")
    config_path = config_dir_root + str(
        ctx.deployment.id) + '/' + component

    if os.path.exists(config_path):
        shutil.rmtree(config_path)


@operation
def upgrade(**kwargs):
    config_dir_root = str(ctx.node.properties['config_dir'])
    componentName = ctx.node.properties['component_name']
    namespace = ctx.node.properties['namespace']
    repo_user = kwargs['repo_user']
    repo_user_passwd = kwargs['repo_user_passwd']
    configJson = kwargs['config']
    chartRepo = kwargs['chart_repo']
    chartVersion = kwargs['chart_version']
    config_set = kwargs['config_set']
    config_json = kwargs['config_json']
    config_url = kwargs['config_url']
    config_format = kwargs['config_format']
    config_path = config_dir_root + str(
        ctx.deployment.id) + '/' + componentName + '/'

    # ctx.logger.debug('debug ' + str(configJson))
    chartName = namespace + "-" + componentName
    chart = chartRepo + "/" + componentName + "-" + chartVersion + ".tgz"

    config_opt_f = ""
    if config_json == '' and config_url == '':
        ctx.logger.debug("Will use default HELM values")
    elif config_json == '' and config_url != '':
        config_opt_f = get_rem_config(config_url, config_format, config_path, config_opt_f, "ru", repo_user, repo_user_passwd)
    elif config_json != '' and config_url == '':
        config_opt_f = get_config_json(config_json, config_path, config_opt_f, "lu")
    else:
        raise NonRecoverableError("Unable to get upgrade config input")

    config_upd = ""
    if config_url != '' or config_json != '':
        config_upd = config_path + ".config_upd"
        gen_config_str(config_upd, config_opt_f)

    config_upd_set = ""
    if config_set != '':
        config_upd_set = config_path + ".config_upd_set"
        config_opt_set = " --set " + config_set
        gen_config_str(config_upd_set, config_opt_set)

    upgradeCommand = 'helm upgrade ' + chartName + ' ' + repo(chart, repo_user, repo_user_passwd) + opt(config_upd) + \
                         opt(config_upd_set) + tiller_host() + tls()

    output = execute_command(upgradeCommand)
    if output == False:
        return ctx.operation.retry(
            message='helm upgrade failed, re-try after 5 second ',
            retry_after=5)
    get_current_helm_value(chartName)
    get_helm_history(chartName)


@operation
def rollback(**kwargs):
    # rollback to some revision
    componentName = ctx.node.properties['component_name']
    namespace = ctx.node.properties['namespace']
    revision = kwargs['revision']
    # configure_admin_conf()
    chartName = namespace + "-" + componentName
    rollbackCommand = 'helm rollback ' + chartName + ' ' + revision + tiller_host() + tls()
    output = execute_command(rollbackCommand)
    if output == False:
        return ctx.operation.retry(
            message='helm rollback failed, re-try after 5 second ',
            retry_after=5)
    get_current_helm_value(chartName)
    get_helm_history(chartName)

@operation
def status(**kwargs):
    componentName = ctx.node.properties['component_name']
    namespace = ctx.node.properties['namespace']

    chartName = namespace + "-" + componentName
    statusCommand = 'helm status ' + chartName + tiller_host() + tls()
    output = execute_command(statusCommand)
    if output == False:
        return ctx.operation.retry(
            message='helm status failed, re-try after 5 second ',
            retry_after=5)

    status_output = [line.strip() for line in output.split('\n') if
                            line.strip()]
    for index in range(len(status_output)):
        status_output[index] = status_output[index].replace('\t', ' ')
    ctx.instance.runtime_properties['install-status'] = status_output
