#!/bin/bash

# ================================================================================
# Copyright (c) 2017 AT&T Intellectual Property. All rights reserved.
# ================================================================================
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.
# ============LICENSE_END=========================================================
#
# ECOMP is a trademark and service mark of AT&T Intellectual Property.

cfy executions start -d cdap_hello_world -w execute_operation -p '{"operation" : "reconfiguration.app_config_reconfigure", "node_ids" : ["hw_cdap_app"], "operation_kwargs" : {"new_config_template" : {"foo":"bar-manual-update"}}, "allow_kwargs_override": true}'
cfy executions start -d cdap_hello_world -w execute_operation -p '{"operation" : "reconfiguration.app_preferences_reconfigure", "node_ids" : ["hw_cdap_app"], "operation_kwargs" : {"new_config_template" : {"foo_updated":"foo-pref-manual-update"}}, "allow_kwargs_override": true}'
cfy executions start -d cdap_hello_world -w execute_operation -p '{"operation" : "reconfiguration.app_smart_reconfigure", "node_ids" : ["hw_cdap_app"], "operation_kwargs" : {"new_config_template" : {"foo_updated":"SO SMARTTTTTT", "foo":"SO SMART AGAINNNNN"}}, "allow_kwargs_override": true}'
