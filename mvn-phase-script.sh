#!/bin/bash

echo "running script: [$0] for module [$1] at stage [$2]"

MVN_MODULE=$1

echo "=> Prepare environment "
#env
if [ -z "$MVN_DOCKERREG_URL" ]; then
   MVN_DOCKERREG_URL='nexus3.onap.org:10001'
fi
if [ -z "$SETTINGS_FILE" ]; then
   SETTINGS_FILE='settings.xml'
fi


TIMESTAMP=$(date +%C%y%m%dT%H%M%S) 
export BUILD_NUMBER="${TIMESTAMP}"

# expected environment variables 
if [ -z "${MVN_NEXUSPROXY}" ]; then
    echo "MVN_NEXUSPROXY environment variable not set.  Cannot proceed"
    exit
fi
MVN_NEXUSPROXY_HOST=$(echo $MVN_NEXUSPROXY |cut -f3 -d'/' | cut -f1 -d':')


if [ -z "${SETTINGS_FILE}" ]; then
    echo "SETTINGS_FILE environment variable not set.  Cannot proceed"
    exit
fi

if [  ]; then

# login to all docker registries
DOCKER_REPOSITORIES="nexus3.onap.org:10001 nexus3.onap.org:10002 nexus3.onap.org:10003 nexus3.onap.org:10004"
for DOCKER_REPOSITORY in $DOCKER_REPOSITORIES;
do
    USER=$(xpath -e "//servers/server[id='$DOCKER_REPOSITORY']/username/text()" "$SETTINGS_FILE")
    PASS=$(xpath -e "//servers/server[id='$DOCKER_REPOSITORY']/password/text()" "$SETTINGS_FILE")

    if [ -z "$USER" ]; then
        echo "Error: no user provided"
    fi

    if [ -z "$PASS" ]; then
        echo "Error: no password provided"
    fi

    [ -z "$PASS" ] && PASS_PROVIDED="<empty>" || PASS_PROVIDED="<password>"
    echo docker login $DOCKER_REPOSITORY -u "$USER" -p "$PASS_PROVIDED"
    docker login $DOCKER_REPOSITORY -u "$USER" -p "$PASS"
done
fi

# ste up env variables, get ready for template resolution
export ONAPTEMPLATE_RAWREPOURL_org_onap_dcaegen2="${MVN_NEXUSPROXY}/content/sites/raw"
export ONAPTEMPLATE_PYPIURL_org_onap_dcaegen2="${MVN_NEXUSPROXY}/content/sites/pypi"
export ONAPTEMPLATE_DOCKERREGURL_org_onap_dcaegen2="${MVN_DOCKERREG_URL}"
export ONAPTEMPLATE_GITREPO_org_onap_dcaegen2="https://gerrit.onap.org"

# use the version text detect which phase we are in in LF CICD process: verify, merge, or (daily) release
LF_PHASE="verify"

#case "$phase" in
#    verify|merge ) REPO="${NEXUS_RAW}/org.openecomp.dcae.pgaas/deb-snapshots" ;;
#    release ) REPO="${NEXUS_RAW}/org.openecomp.dcae.pgaas/deb-releases" ;;
#esac

# mvn phase in life cycle 
MVN_PHASE="$2"

case $MVN_PHASE in
clean)
  echo "==> clean phase script"
  ;;
generate-sources)
  echo "==> generate-sources phase script. Dir is $(pwd)"

  TEMPLATES=$(env |grep ONAPTEMPLATE)
  echo "====> Resolving the following temaplate from environment variables "
  echo "[$TEMPLATES]"
  SELFFILE=$(echo $0 | rev | cut -f1 -d '/' | rev)
  for TEMPLATE in $TEMPLATES; do
    KEY=$(echo $TEMPLATE | cut -f1 -d'=')
    VALUE=$(echo $TEMPLATE | cut -f2 -d'=')
    VALUE2=$(echo $TEMPLATE | cut -f2 -d'=' |sed 's/\//\\\//g')
    FILES=$(grep -rl "$KEY")

    # assuming FILES is not longer than 2M bytes, the limit for variable value max size on this VM 
    for F in $FILES; do
       if [[ $F == *"$SELFFILE" ]]; then
          continue
       fi
       echo "======> Resolving template $KEY to value $VALUE for file $F"
       sed -i "s/{{[[:space:]]*$KEY[[:space:]]*}}/$VALUE2/g" $F
    done 
    
    #if [ ! -z "$FILES" ]; then
    #   echo "====> Resolving template $VALUE to value $VALUE"
    #   #CMD="grep -rl \"$VALUE\" | tr '\n' '\0' | xargs -0 sed -i \"s/{{[[:space:]]*$VALUE[[:space:]]*}}/$VALUE/g\""
    #   grep -rl "$KEY" | tr '\n' '\0' | xargs -0 sed -i 's/$KEY/$VALUE2/g'
    #   #echo $CMD
    #   #eval $CMD
    #fi
  done
  echo "====> Done template reolving"
  ;;
compile)
  echo "==> compile phase script"
  ;;
test)
  echo "==> test phase script"
  ;;
package)
  echo "==> package phase script"
  ;;
install)
  echo "==> install phase script"
  ;;
deploy)
  echo "==> deploy phase script"

  # prepare credential for curl use (raw repo)
  USER=$(xpath -q -e "//servers/server[id='ecomp-raw']/username/text()" "$SETTINGS_FILE")
  PASS=$(xpath -q -e "//servers/server[id='ecomp-raw']/password/text()" "$SETTINGS_FILE")
  export NETRC=$(mktemp)
  echo "machine $MVN_NEXUSPROXY_HOST login ${USER} password ${PASS}" >> "${NETRC}"
  set -x; curl -k --netrc-file '${NETRC}' --upload-file '{0}' '${REPO}/{2}-{1}'



  # login to all docker registries
  USER=$(xpath -e "//servers/server[id='$MVN_DOCKERREG_URL']/username/text()" "$SETTINGS_FILE")
  PASS=$(xpath -e "//servers/server[id='$MVN_DOCKERREG_URL']/password/text()" "$SETTINGS_FILE")
  if [ -z "$USER" ]; then
    echo "Error: no user provided"
  fi
  if [ -z "$PASS" ]; then
    echo "Error: no password provided"
  fi
  [ -z "$PASS" ] && PASS_PROVIDED="<empty>" || PASS_PROVIDED="<password>"
  echo docker login $MVN_DOCKERREG_URL -u "$USER" -p "$PASS_PROVIDED"
  docker login $MVN_DOCKERREG_URL -u "$USER" -p "$PASS"

  #docker push
  ;;
*)
  echo "==> unprocessed phase"
  ;;
esac

