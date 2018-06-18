# Change Log

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](http://keepachangelog.com/) 
and this project adheres to [Semantic Versioning](http://semver.org/).



## [1.2.0]
* Enhancement: Use the "healthcheck" parameters from node_properties to set up a 
Kubernetes readiness probe for the container.

## [1.1.0]
* Enhancement: When Cloudify Manager is running in a Docker container in a Kubernetes environment, the plugin can use the Kubernetes API credentials set up by Kubernetes.

## [1.0.1]
* Fixes a bug in passing environment variables.

## [1.0.0]

* Initial release of the Kubernetes plugin.  It is built on the [Docker plugin](../docker) and preserves the Docker plugin's integration with the policy plugin and the DMaaP plugin.
