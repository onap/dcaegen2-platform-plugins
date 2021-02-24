from uritools import urisplit
from fqdn import FQDN
import validators
from validators.utils import ValidationFailure

class SansParser:
    def parse_sans(self, sans):
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
        fqdn = FQDN(san, min_labels = 1)
        return fqdn.is_valid
