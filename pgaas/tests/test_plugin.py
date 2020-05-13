# ============LICENSE_START====================================================
# org.onap.ccsdk
# =============================================================================
# Copyright (c) 2017-2018 AT&T Intellectual Property. All rights reserved.
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

"""
unit tests for PostgreSQL password plugin
"""

from __future__ import print_function
# pylint: disable=import-error,unused-import,wrong-import-order
import pytest
import socket
import psycopg2
import pgaas.pgaas_plugin
from cloudify.mocks import MockCloudifyContext
from cloudify.mocks import MockNodeContext
from cloudify.mocks import MockNodeInstanceContext
from cloudify.mocks import MockRelationshipSubjectContext
from cloudify.state import current_ctx
from cloudify.exceptions import NonRecoverableError
from cloudify import ctx

import sys
import os
sys.path.append(os.path.realpath(os.path.dirname(__file__)))
import traceback

TMPNAME = "/tmp/pgaas_plugin_tests_{}".format(os.environ["USER"] if "USER" in os.environ else
                                              os.environ["LOGNAME"] if "LOGNAME" in os.environ else
                                              str(os.getuid()))

class MockKeyPair(object):
  """
  mock keypair for cloudify contexts
  """
  def __init__(self, type_hierarchy=None, target=None):
    self._type_hierarchy = type_hierarchy
    self._target = target

  @property
  def type_hierarchy(self):
    """
    return the type hierarchy
    """
    return self._type_hierarchy

  @property
  def target(self):
    """
    return the target
    """
    return self._target

class MockInstance(object): # pylint: disable=too-few-public-methods
  """
  mock instance for cloudify contexts
  """
  def __init__(self, instance=None):
    self._instance = instance

  @property
  def instance(self):
    """
    return the instance
    """
    return self._instance

class MockRuntimeProperties(object): # pylint: disable=too-few-public-methods
  """
  mock runtime properties for cloudify contexts
  """
  def __init__(self, runtime_properties=None):
    self._runtime_properties = runtime_properties

  @property
  def runtime_properties(self):
    """
    return the properties
    """
    return self._runtime_properties

class MockSocket(object):
  """
  mock socket interface
  """
  def __init__(self):
    pass
  def connect(self, host=None, port=None):
    """
    mock socket connection
    """
    pass
  def close(self):
    """
    mock socket close
    """
    pass


def _connect(host, port): # pylint: disable=unused-argument
  """
  mock connection
  """
  return {}

def set_mock_context(msg, monkeypatch, writerfqdn='test.bar.example.com'):
  """
  establish the mock context for our testing
  """
  print("================ %s ================" % msg)
  # pylint: disable=bad-continuation
  props = {
    'writerfqdn': writerfqdn,
    'use_existing': False,
    'readerfqdn': 'test-ro.bar.example.com',
    'name': 'testdb',
    'port': '5432',
    'initialpassword': 'test'
    }

  sshkeyprops = {
    'public': "testpub",
    'base64private': "testpriv"
    }

  mock_ctx = MockCloudifyContext(node_id='test_node_id', node_name='test_node_name',
                                 # pylint: disable=bad-whitespace
                                 properties=props,
                                 relationships = [
                                   MockKeyPair(type_hierarchy =
                                               [ "dcae.relationships.pgaas_cluster_uses_sshkeypair" ],
                                               target= MockInstance(
                                                 MockRuntimeProperties(sshkeyprops)) )
                                   ],
                                 runtime_properties = {
                                   "admin": { "user": "admin_user" },
                                   "user": { "user": "user_user" },
                                   "viewer": { "user": "viewer_user" }
                                   }
                                 )
  current_ctx.set(mock_ctx)
  monkeypatch.setattr(socket.socket, 'connect', _connect)
  # monkeypatch.setattr(psycopg2, 'connect', _connect)
  pgaas.pgaas_plugin.setOptManagerResources(TMPNAME)
  return mock_ctx


@pytest.mark.dependency()
def test_start(monkeypatch): # pylint: disable=unused-argument
  """
  put anything in here that needs to be done
  PRIOR to the tests
  """
  pass

@pytest.mark.dependency(depends=['test_start'])
def test_add_pgaas_cluster(monkeypatch):
  """
  test add_pgaas_cluster()
  """
  try:
    set_mock_context('test_add_pgaas_cluster', monkeypatch)
    pgaas.pgaas_plugin.add_pgaas_cluster(args={})
  except Exception as e:
    print("Error: {0}".format(e))
    print("Stack: {0}".format(traceback.format_exc()))
    raise
  finally:
    current_ctx.clear()

@pytest.mark.dependency(depends=['test_add_pgaas_cluster'])
def test_add_database(monkeypatch):
  """
  test add_database()
  """
  try:
    set_mock_context('test_add_database', monkeypatch)
    pgaas.pgaas_plugin.create_database(args={})
  except Exception as e:
    print("Error: {0}".format(e))
    print("Stack: {0}".format(traceback.format_exc()))
    raise
  finally:
    current_ctx.clear()

@pytest.mark.dependency(depends=['test_add_pgaas_cluster'])
def test_bad_add_database(monkeypatch):
  """
  test bad_add_database()
  """
  try:
    set_mock_context('test_add_database', monkeypatch, writerfqdn="bad.bar.example.com")
    with pytest.raises(NonRecoverableError):
      pgaas.pgaas_plugin.create_database(args={})
  except Exception as e:
    print("Error: {0}".format(e))
    print("Stack: {0}".format(traceback.format_exc()))
    raise
  finally:
    current_ctx.clear()

@pytest.mark.dependency(depends=['test_add_database'])
def test_update_database(monkeypatch):
  """
  test update_database()
  """
  try:
    ########################################################
    # Subtle test implications regarding: update_database  #
    # ---------------------------------------------------  #
    # 1)  update_database is a workflow and the context    #
    #     passed to it has 'nodes' attribute which is not  #
    #     not included in MockCloudifyContext              #
    # 2)  the 'nodes' attribute is a list of contexts so   #
    #     we will have to create a sub-context             #
    # 3)  update_database will iterate through each of the #
    #     nodes contexts looking for the correct one       #
    # 4)  To identify the correct sub-context it will first#
    #     check each sub-context for the existence of      #
    #     properties attribute                             #
    # 5)  ****Mock_context internally saves properties as  #
    #     variable _properties and 'properties' is defined #
    #     as @property...thus it is not recognized as an   #
    #     attribute...this will cause update_database to   #
    #     fail so we need to explicitly create properties  #
    #     properties attribute in the subcontext           #
    ########################################################

    ####################
    # Main context     #
    ####################
    myctx = set_mock_context('test_update_database', monkeypatch)
    ###########################################################
    # Create subcontext and assign it to attribute properties #
    # in main context                                         #
    ###########################################################
    mynode = set_mock_context('test_update_database_node', monkeypatch)
    # pylint: disable=protected-access
    mynode.properties = mynode._properties
    myctx.nodes = [mynode]
    pgaas.pgaas_plugin.update_database(refctx=myctx)
  except Exception as e:
    print("Error: {0}".format(e))
    print("Stack: {0}".format(traceback.format_exc()))
    raise
  finally:
    current_ctx.clear()

@pytest.mark.dependency(depends=['test_update_database'])
def test_delete_database(monkeypatch):
  """
  test delete_database()
  """
  try:
    set_mock_context('test_delete_database', monkeypatch)
    pgaas.pgaas_plugin.delete_database(args={})
  except Exception as e:
    print("Error: {0}".format(e))
    print("Stack: {0}".format(traceback.format_exc()))
    raise
  finally:
    current_ctx.clear()

@pytest.mark.dependency(depends=['test_delete_database'])
def test_rm_pgaas_cluster(monkeypatch):
  """
  test rm_pgaas_cluster()
  """
  try:
    set_mock_context('test_rm_pgaas_cluster', monkeypatch)
    pgaas.pgaas_plugin.rm_pgaas_cluster(args={})
  except Exception as e:
    print("Error: {0}".format(e))
    print("Stack: {0}".format(traceback.format_exc()))
    raise
  finally:
    current_ctx.clear()
