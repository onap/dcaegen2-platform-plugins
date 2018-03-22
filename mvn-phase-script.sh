#!/bin/bash

# ================================================================================
# Copyright (c) 2017-2018 AT&T Intellectual Property. All rights reserved.
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

set -ex


echo "running script: [$0] for module [$1] at stage [$2]"

MVN_PROJECT_MODULEID="$1"
MVN_PHASE="$2"

PROJECT_ROOT=$(dirname $0)

set -e
if ! wget -O ${PROJECT_ROOT}/mvn-phase-lib.sh \
  "$MVN_RAWREPO_BASEURL_DOWNLOAD"/org.onap.dcaegen2.utils/R2/scripts/mvn-phase-lib.sh; then
  cp "${PROJECT_ROOT}"/scripts/mvn-phase-lib.sh "${PROJECT_ROOT}/mvn-phase-lib.sh"
fi
source "${PROJECT_ROOT}"/mvn-phase-lib.sh


# Customize the section below for each project
case $MVN_PHASE in
clean)
  echo "==> clean phase script"
  clean_templated_files
  clean_tox_files
  rm -rf ./venv-* ./*.wgn ./site
  ;;
generate-sources)
  echo "==> generate-sources phase script"
  expand_templates
  ;;
compile)
  echo "==> compile phase script"
  ;;
test)
  echo "==> test phase script"
  run_tox_test
  ;;
package)
  echo "==> package phase script"
  case $MVN_PROJECT_MODULEID in
  cdap|dcae-policy|docker|relationships|k8s)
    build_archives_for_wagons
    build_wagons
    ;;
  *)
    ;;
  esac
  ;;
install)
  echo "==> install phase script"
  ;;
deploy)
  echo "==> deploy phase script"
  case $MVN_PROJECT_MODULEID in
  cdap|dcae-policy|docker|relationships|k8s)
    upload_wagons_and_type_yamls
    upload_wagon_archives
    ;;
  *)
    ;;
  esac
  ;;
*)
  echo "==> unprocessed phase"
  ;;
esac
