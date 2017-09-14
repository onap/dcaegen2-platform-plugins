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

from cdapcloudify.cdap_plugin import _validate_conns, BadConnections
import pytest

#todo.. add more tests.. #shame

def _get_good_connection():
    connections = {}
    connections["streams_publishes"] = [
      {"name"        : "test_n",                     
       "location"    : "test_l",
       "client_role" : "test_cr",
       "type"        : "message_router",
       "config_key"  : "test_c",
       "aaf_username": "test_u",
       "aaf_password": "test_p" 
      },
      {"name"        : "test_n2",                     
       "location"    : "test_l",
       "client_role" : "test_cr",
       "type"        : "message_router",
       "config_key"  : "test_c",
       "aaf_username": "test_u",
       "aaf_password": "test_p" 
      },
      {"name"       : "test_feed00",                      
       "location"   : "test_l",
       "type"       : "data_router",
       "config_key" : "mydrconfigkey"
      }
    ]
    connections["streams_subscribes"] = [
       {"name"        : "test_n",                     
       "location"    : "test_l",
       "client_role" : "test_cr",
       "type"        : "message_router",
       "config_key"  : "test_c",
       "aaf_username": "test_u",
       "aaf_password": "test_p" 
      },
      {"name"        : "test_n2",                     
       "location"    : "test_l",
       "client_role" : "test_cr",
       "type"        : "message_router",
       "config_key"  : "test_c",
       "aaf_username": "test_u",
       "aaf_password": "test_p" 
      }
    ]
    return connections

def test_validate_cons():
    #test good streams
    good_conn = _get_good_connection() 
    _validate_conns(good_conn)

    #mutate
    nosub = _get_good_connection().pop("streams_subscribes")
    with pytest.raises(BadConnections) as excinfo:
       _validate_conns(nosub)

    nopub = _get_good_connection().pop("streams_publishes")
    with pytest.raises(BadConnections) as excinfo:
        _validate_conns(nopub)

    noloc = _get_good_connection()["streams_publishes"][0].pop("location")
    with pytest.raises(BadConnections) as excinfo:
        _validate_conns(noloc)

