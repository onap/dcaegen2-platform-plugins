# ============LICENSE_START=======================================================
# org.onap.dcae
# ================================================================================
# Copyright (c) 2021 Nokia. All rights reserved.
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

# import pytest

SAMPLE_SANS_INPUT = "example.org,test.onap.org,onap@onap.org,127.0.0.1,[2001:0db8:85a3:0000:0000:8a2e:0370:7334],onap://cluster.local/"


def test_parse_dns_name():
    from k8sclient.sans_parser import SansParser
    result = SansParser().parse_sans(SAMPLE_SANS_INPUT)
    dnss_array = result["dnss"]
    assert len(dnss_array) == 3
    assert assert_item_in_list("example.org", dnss_array)


def test_parse_ips():
    from k8sclient.sans_parser import SansParser
    result = SansParser().parse_sans(SAMPLE_SANS_INPUT)
    ips_array = result["ips"]
    assert len(ips_array) == 2
    assert assert_item_in_list("127.0.0.1", ips_array)
    assert assert_item_in_list("[2001:0db8:85a3:0000:0000:8a2e:0370:7334]",
                               ips_array)


def test_parse_emails():
    from k8sclient.sans_parser import SansParser
    result = SansParser().parse_sans(SAMPLE_SANS_INPUT)
    emails_array = result["emails"]
    assert len(emails_array) == 1
    assert assert_item_in_list("onap@onap.org", emails_array)


def test_parse_uri():
    from k8sclient.sans_parser import SansParser
    result = SansParser().parse_sans(SAMPLE_SANS_INPUT)
    uris_array = result["uris"]
    assert len(uris_array) == 1
    assert assert_item_in_list("onap://cluster.local/", uris_array)


def assert_item_in_list(item, list):
    if item in list:
        return True
    else:
        return False
