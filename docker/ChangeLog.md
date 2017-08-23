# Change Log

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](http://keepachangelog.com/) 
and this project adheres to [Semantic Versioning](http://semver.org/).

## [2.3.0]

* Rip out dockering and use common python-dockering library
    - Using 1.2.0 of python-dockering supports Docker exec based health checks
* Support mapping ports and volumes when provided in docker config

## [2.2.0]

* Add `dcae.nodes.DockerContainerForComponentsUsingDmaap` node type and parse streams_publishes and streams_subscribes to be used by the DMaaP plugin.
    - Handle message router wiring in the create operation for components
    - Handle data router wiring in the create and in the start operation for components
* Refactor the create operations and the start operations for components. Refactored to be functional to enable for better unit test coverage.
* Add decorators for common cross cutting functionality
* Add example blueprints for different dmaap cases

## [2.1.0]

* Add the node type `DockerContainerForPlatforms` which is intended for platform services who are to have well known names and ports
* Add backdoor for `DockerContainerForComponents` to statically map ports
* Add hack fix to allow this plugin access to the research nexus
* Add support for dns through the local Consul agent
* Free this plugin from the CentOS bondage

## [2.0.0]

* Remove the magic env.ini code.  It's no longer needed because we are now running local agents of Consul.
* Save and use the docker container id
* `DockerContainer` is now a different node type that is much simpler than `DockerContainerforComponents`.  It is targeted for the use case of registrator.  This involved overhauling the create and start container functionality.
* Classify connection and docker host not found error as recoverable
* Apply CONSUL_HOST to point to the local Consul agent

## [1.0.0]

* Implement health checks - expose health checks on the node and register Docker containers with it.  Note that health checks are currently optional.
* Add option to remove images in the stop operation
* Verify that the container is running and healthy before finishing the start operation
* Image names passed in are now required to be the fully tagged names including registry
* Remove references to rework in the code namespaces
* Application configuration is now a YAML map to accomodate future blueprint generation
* Update blueprints and cfyhelper.sh 
