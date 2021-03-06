# ============LICENSE_START=======================================================
# org.onap.dcae
# ================================================================================
# Copyright (c) 2018-2020 AT&T Intellectual Property. All rights reserved.
# Copyright (c) 2019 Pantheon.tech. All rights reserved.
# Copyright (c) 2020-2021 Nokia. All rights reserved.
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

_CONFIG_PATH = "/opt/onap/config.txt"   # Path to config file on the Cloudify Manager host
_CONSUL_KEY = "k8s-plugin"              # Key under which CM configuration is stored in Consul

# Default configuration values
DCAE_NAMESPACE = "dcae"
CONSUL_DNS_NAME = "consul"
DEFAULT_K8S_LOCATION = "central"
DEFAULT_MAX_WAIT = 1800

FB_LOG_PATH = "/var/log/onap"
FB_DATA_PATH = "/usr/share/filebeat/data"
FB_CONFIG_PATH = "/usr/share/filebeat/filebeat.yml"
FB_CONFIG_SUBPATH = "filebeat.yml"
FB_CONFIG_MAP = "filebeat-conf"
FB_IMAGE = "docker.elastic.co/beats/filebeat:5.5.0"

TLS_CERT_PATH = "/opt/app/osaaf"
TLS_IMAGE = "nexus3.onap.org:10001/onap/org.onap.dcaegen2.deployments.tls-init-container:2.1.0"
TLS_COMP_CERT_PATH = "/opt/dcae/cacert"
TLS_CA_CONFIGMAP = "dcae-cacert-configmap"

EXT_TLS_IMAGE = "nexus3.onap.org:10001/onap/org.onap.oom.platform.cert-service.oom-certservice-client:2.1.0"
EXT_TLS_REQUEST_URL = "https://oom-cert-service:8443/v1/certificate/"
EXT_TLS_TIMEOUT = "30000"
EXT_TLS_COUNTRY = "US"
EXT_TLS_ORGANIZATION = "Linux-Foundation"
EXT_TLS_STATE = "California"
EXT_TLS_ORGANIZATIONAL_UNIT = "ONAP"
EXT_TLS_LOCATION = "San-Francisco"
EXT_TLS_CERT_SECRET_NAME = "oom-cert-service-client-tls-secret"
EXT_TLS_KEYSTORE_PASSWORD_SECRET_NAME = "oom-cert-service-keystore-password"
EXT_TLS_TRUSTSTORE_PASSWORD_SECRET_NAME = "oom-cert-service-truststore-password"
EXT_TLS_KEYSTORE_SECRET_KEY = "keystore.jks"
EXT_TLS_TRUSTSTORE_SECRET_KEY = "truststore.jks"
EXT_TLS_KEYSTORE_PASSWORD_SECRET_KEY = "password"
EXT_TLS_TRUSTSTORE_PASSWORD_SECRET_KEY = "password"

CERT_POST_PROCESSOR_IMAGE = "nexus3.onap.org:10001/onap/org.onap.oom.platform.cert-service.oom-certservice-post-processor:2.1.0"
CBS_BASE_URL = "https://config-binding-service:10443/service_component_all"

CMPV2_ISSUER_ENABLED = "false"
CMPV2_ISSUER_NAME = "cmpv2-issuer-onap"

def _set_defaults():
    """ Set default configuration parameters """
    return {
        "namespace" : DCAE_NAMESPACE,                   # k8s namespace to use for DCAE
        "consul_dns_name" : CONSUL_DNS_NAME,            # k8s internal DNS name for Consul
        "default_k8s_location" : DEFAULT_K8S_LOCATION,  # default k8s location to deploy components
        "image_pull_secrets" : [],                      # list of k8s secrets for accessing Docker registries
        "max_wait": DEFAULT_MAX_WAIT,                   # Default maximum time to wait for component to become healthy (secs)
        "filebeat": {                                   # Configuration for setting up filebeat container
            "log_path" : FB_LOG_PATH,                   # mount point for log volume in filebeat container
            "data_path" : FB_DATA_PATH,                 # mount point for data volume in filebeat container
            "config_path" : FB_CONFIG_PATH,             # mount point for config volume in filebeat container
            "config_subpath" : FB_CONFIG_SUBPATH,       # subpath for config data in filebeat container
            "config_map" : FB_CONFIG_MAP,               # ConfigMap holding the filebeat configuration
            "image": FB_IMAGE                           # Docker image to use for filebeat
        },
        "tls": {                                        # Configuration for setting up TLS
            "cert_path" : TLS_CERT_PATH,                # mount point for certificate volume in TLS init container
            "image": TLS_IMAGE,                         # Docker image to use for TLS init container
            "component_cert_dir": TLS_COMP_CERT_PATH    # default mount point for certificate volume in component container
        },
        "external_cert": {
            "image_tag": EXT_TLS_IMAGE,                           # Docker image to use for external TLS init container
            "request_url" : EXT_TLS_REQUEST_URL,                  # URL to Cert Service API
            "timeout" : EXT_TLS_TIMEOUT,                          # Request timeout
            "country" : EXT_TLS_COUNTRY,                          # Country name in ISO 3166-1 alpha-2 format, for which certificate will be created
            "organization" : EXT_TLS_ORGANIZATION,                # Organization name, for which certificate will be created
            "state" : EXT_TLS_STATE,                              # State name, for which certificate will be created
            "organizational_unit" : EXT_TLS_ORGANIZATIONAL_UNIT,  # Organizational unit name, for which certificate will be created
            "location" : EXT_TLS_LOCATION,                        # Location name, for which certificate will be created
            "cert_secret_name": EXT_TLS_CERT_SECRET_NAME,         # Name of secret containing keystore and truststore for secure communication of Cert Service Client and Cert Service
            "keystore_secret_key" : EXT_TLS_KEYSTORE_SECRET_KEY,  # Key for keystore value exists in secret (cert_secret_name)
            "truststore_secret_key" : EXT_TLS_TRUSTSTORE_SECRET_KEY,   # Key for truststore value exists in secret (cert_secret_name)
            "keystore_password_secret_name": EXT_TLS_KEYSTORE_PASSWORD_SECRET_NAME, # Name of secret containing password for keystore for secure communication of Cert Service Client and Cert Service
            "truststore_password_secret_name": EXT_TLS_TRUSTSTORE_PASSWORD_SECRET_NAME, # Name of secret containing password for truststore for secure communication of Cert Service Client and Cert Service
            "keystore_password_secret_key" : EXT_TLS_KEYSTORE_PASSWORD_SECRET_KEY,      # Key for keystore password value exists in secret (keystore_password_secret_name)
            "truststore_password_secret_key" : EXT_TLS_TRUSTSTORE_PASSWORD_SECRET_KEY   # Key for truststore password value exists in secret (truststore_password_secret_name)

        },
        "cert_post_processor": {
            "image_tag": CERT_POST_PROCESSOR_IMAGE      # Docker image to use for cert post processor init container
        },
        "cbs": {
            "base_url" : CBS_BASE_URL                   # URL prefix for accessing config binding service
        },
        "cmpv2_issuer": {
            "enabled": CMPV2_ISSUER_ENABLED,
            "name":    CMPV2_ISSUER_NAME
        }
    }

def configure(config_path=_CONFIG_PATH, key = _CONSUL_KEY):
    """
    Get configuration information from local file and Consul.
    Note that the Cloudify context ("ctx") isn't available at
    module load time.
    """

    from cloudify.exceptions import NonRecoverableError
    try:
        import configparser
    except ImportError:
        import ConfigParser as configparser
    from k8splugin import discovery
    config = _set_defaults()

    try:
        # Get Consul address from a config file
        c = configparser.ConfigParser()
        c.read(config_path)
        config["consul_host"] = c.get('consul','address')

        # Get the rest of the config from Consul
        conn = discovery.create_kv_conn(config["consul_host"])
        val = discovery.get_kv_value(conn, key)

        # Merge Consul results into the config
        config.update(val)

    except discovery.DiscoveryKVEntryNotFoundError as e:
        # Don't reraise error, assume defaults are wanted.
        pass

    except Exception as e:
        raise NonRecoverableError(e)

    return config
