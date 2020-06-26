# Change Log

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](http://keepachangelog.com/)
and this project adheres to [Semantic Versioning](http://semver.org/).

## [3.1.0]
* DCAEGEN2-2252 - Add support to request certificates from CMPv2 server in DCAE cloudify blueprints

## [3.0.0]
* DCAEGEN2-1791 - eliminate the ContainerizedPlatformComponent type
* DCAEGEN2-2215 - allow environment variables to be set via docker_config

## [1.7.2]
* DCAEGEN2-2006 Reduce code complexity
 The k8sclient.k8sclient.deploy function parameter 'resources' is now an optional
 keyword argument, i.e. it must be passed named and not as a positional argument.

## [1.7.1]
* DCAEGEN2-1988 Customize python import for kubernetes plugin

## [1.7.0]
* DCAEGEN2-1956 support python3 in all plugins

## [1.4.13]
 Fix bug related to setting the delivery URL for a DR subscriber.  (DCAEGEN2-1009)

## [1.4.12]
 Change location of kubeconfig file for multi-cluster support.  Put the
 file in a subdirectory so that the k8s volume mount does not require a
 "subPath" parameter, so that updates to the ConfigMap hosting the kubeconfig
 will be visible to the plugin without restarting Cloudify Manager.

## [1.4.11]
 change v['container']['mode'] to v['container'].get('mode') to allow for
 the 'mode' value to be absent from v['container']
 add comment: The name segment is required and must be 63 characters or less
 (https://kubernetes.io/docs/concepts/overview/working-with-objects/labels/)

## [1.4.10]
 Support for deploying to multiple Kubernetes clusters.

## [1.4.9]
* Support for liveness probes (https://kubernetes.io/docs/tasks/configure-pod-container/configure-liveness-readiness-probes/)
* fix the readiness probe to run script such as "/opt/app/snmptrap/bin/snmptrapd.sh status"
* change "ports" and the "mode" of volume to be optional instead of mandatory

## [1.4.8]
* If an installation step times out because a component does not become ready within the maximum wait time,
delete the Kubernetes artifacts associated with the component.  Previously, an installation step might time
out due to a very slow image pull.  Cloudify would report a failure, but the component would come up, much
later, after Kubernetes finished pulling the image.   This should no longer happen.

## [1.4.7]
* Increase unit test coverage

## [1.4.6]
* Support for specifying CPU and memory resources in a blueprint for a containerized component
* Changes the default time that the plugin will wait for a container to become ready from 300 seconds to 1800 seconds

## [1.4.5]
* DCAEGEN2-1086 update onap-dcae-dcaepolicy-lib version to avoid Consul stores under old service_component_name

## [1.3.0]
* Enhancement: Add support for changing the image running in the application container.  ("Rolling upgrade")

## [1.2.0]
* Enhancement: Use the "healthcheck" parameters from node_properties to set up a
Kubernetes readiness probe for the container.

## [1.1.0]
* Enhancement: When Cloudify Manager is running in a Docker container in a Kubernetes environment, the plugin can use the Kubernetes API credentials set up by Kubernetes.

## [1.0.1]
* Fixes a bug in passing environment variables.

## [1.0.0]

* Initial release of the Kubernetes plugin.  It is built on the [Docker plugin](../docker) and preserves the Docker plugin's integration with the policy plugin and the DMaaP plugin.
