# ============LICENSE_START====================================================
# org.onap.ccsdk
# =============================================================================
# Copyright (c) 2017,2020 AT&T Intellectual Property. All rights reserved.
# =============================================================================
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
# ============LICENSE_END======================================================

import uuid
import os
from cloudify import ctx
from cloudify.decorators import operation

@operation(resumable=True)
def generate(**kwargs):
  """
  Create SSH key pair
  """
  tmpdir = '/tmp/{0}'.format(uuid.uuid4().hex)
  os.mkdir(tmpdir, 0o700)
  os.system('ssh-keygen -t rsa -b 2048 -C "hadoop@cdapcluster" -N "" -f {0}/id_rsa'.format(tmpdir))
  os.system('base64 -w 0 <{0}/id_rsa >{0}/id64'.format(tmpdir))
  with open('{0}/id64'.format(tmpdir), 'r') as f:
    k64 = f.read()
  with open('{0}/id_rsa.pub'.format(tmpdir), 'r') as f:
    pub = f.read()
  os.system('rm -rf {0}'.format(tmpdir))
  ctx.instance.runtime_properties['public'] = pub.strip()
  ctx.instance.runtime_properties['base64private'] = k64.strip()
