# ============LICENSE_START=======================================================
# org.onap.dcae
# ================================================================================
# Copyright (c) 2017-2020 AT&T Intellectual Property. All rights reserved.
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

def test_random_string(mockconfig):
    from k8splugin import utils

    target_length = 10
    assert len(utils.random_string(target_length)) == target_length


def test_update_dict(mockconfig):
    from k8splugin import utils

    d = { "a": 1, "b": 2 }
    u = { "a": 2, "b": 3 }
    assert utils.update_dict(d, u) == u
