# ============LICENSE_START====================================================
# org.onap.ccsdk
# =============================================================================
# Copyright (c) 2017 AT&T Intellectual Property. All rights reserved.
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

This is a mock psycopg2 module.

"""

class MockCursor(object):
  """
  mocked cursor
  """
  def __init__(self, **kwargs):
    pass

  def execute(self, cmd, exc=None):
    """
    mock SQL execution
    """
    pass

  def close(self):
    """
    mock SQL close
    """
    pass

  def __iter__(self):
    return iter([])

class MockConn(object): # pylint: disable=too-few-public-methods
  """
  mock SQL connection
  """
  def __init__(self, **kwargs):
    pass

  def __enter__(self):
    return self

  def __exit__(self, exc_type, exc_value, traceback):
    pass

  def cursor(self): # pylint: disable=no-self-use
    """
    mock return a cursor
    """
    return MockCursor()

def connect(**kwargs): # pylint: disable=unused-argument
  """
  mock get-a-connection
  """
  return MockConn()
