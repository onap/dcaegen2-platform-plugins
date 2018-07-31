# ============LICENSE_START=======================================================
# org.onap.dcae
# ================================================================================
# Copyright (c) 2018 AT&T Intellectual Property. All rights reserved.
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

import pytest

def test_parse_interval():
    from k8sclient.k8sclient import _parse_interval

    good_intervals = [{"in": input, "ex": expected}
        for (input, expected) in [
            (30, 30),
            ("30", 30),
            ("30s", 30),
            ("2m", 2 * 60),
            ("2h", 2 * 60 * 60),
            ("24h", 24 * 60 * 60),
            (354123, 354123),
            ("354123", 354123),
            ("354123s", 354123),
            (1234567890123456789012345678901234567890L,1234567890123456789012345678901234567890L),
            ("1234567890123456789012345678901234567890",1234567890123456789012345678901234567890L),
            ("1234567890123456789012345678901234567890s",1234567890123456789012345678901234567890L),
            ("05s", 5),
            ("00000000000000000000000000000000005m", 5 * 60)
        ]
    ]

    bad_intervals = [
        -99,
        "-99",
        "-99s",
        "-99m",
        "-99h",
        "30d",
        "30w",
        "30y",
        "3 0s",
        "3 5m",
        30.0,
        "30.0s",
        "30.0m",
        "30.0h",
        "a 30s",
        "30s a",
        "a 30s a",
        "a 30",
        "30 a",
        "a 30 a",
        "i want an interval of 30s",
        "thirty seconds",
        "30 s",
        "30 m",
        "30 h",
        10E0,
        "10E0",
        3.14159,
        "3.14159s"
        "3:05",
        "3m05s",
        "3seconds",
        "3S",
        "1minute",
        "1stanbul"
    ]

    for test_case in good_intervals:
        assert _parse_interval(test_case["in"]) == test_case["ex"]

    for interval in bad_intervals:
        with pytest.raises(ValueError):
            _parse_interval(interval)