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

from uritools import urisplit
from fqdn import FQDN
import validators
from validators.utils import ValidationFailure


class SansParser:
    def parse_sans(self, sans):
        """
        Method for parsing sans. As input require SANs separated by comma (,)
        Return Map with sorted SANs by type:
            ips -> IPv4 or IPv6
            dnss -> dns name
            emails -> email
            uris -> uri

        Example usage:
            SansParser().parse_sans("example.org,onap@onap.org,127.0.0.1,onap://cluster.local/")
            Output: {   "ips": [127.0.0.1],
                        "uris": [onap://cluster.local/],
                        "dnss": [example.org],
                        "emails": [onap@onap.org]}
        """
        sans_map = {"ips": [],
                    "uris": [],
                    "dnss": [],
                    "emails": []}
        sans_arr = sans.split(",")
        for san in sans_arr:
            if self._is_ip_v4(san) or self._is_ip_v6(san):
                sans_map["ips"].append(san)
            elif self._is_uri(san):
                sans_map["uris"].append(san)
            elif self._is_email(san):
                sans_map["emails"].append(san)
            elif self._is_dns(san):
                sans_map["dnss"].append(san)
        return sans_map

    def _is_email(self, san):
        try:
            return validators.email(san)
        except ValidationFailure:
            return False

    def _is_ip_v4(self, san):
        try:
            return validators.ipv4(san)
        except ValidationFailure:
            return False

    def _is_ip_v6(self, san):
        try:
            return validators.ipv6(san)
        except ValidationFailure:
            return False

    def _is_uri(self, san):
        parts = urisplit(san)
        return parts.isuri()

    def _is_dns(self, san):
        fqdn = FQDN(san, min_labels=1)
        return fqdn.is_valid
