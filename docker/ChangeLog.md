# Change Log

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](http://keepachangelog.com/) 
and this project adheres to [Semantic Versioning](http://semver.org/).

## [3.3.0]
* DCAEGEN2-1956 support python3 in all plugins

## [3.2.1]
* DCAEGEN2-1086 update onap-dcae-dcaepolicy-lib version to avoid Consul stores under old service_component_name

## [3.2.0]

* Change requirements.txt to use a version range for dcaepolicylib
* DCAEGEN2-442

## [3.1.0]

* DCAEGEN2-415 - Change requirements.txt to use dcaepolicy 2.3.0. *Apparently* this constitutes a version bump.

## [3.0.0]

* Update docker plugin to use dcaepolicy 2.1.0.  This involved all sorts of updates in how policy is expected to work for the component where the updates are not backwards friendly.

## [2.4.0]

* Change *components* to be policy reconfigurable:
    - Add policy execution operation
    - Add policy decorators to task so that application configuration will be merged with policy
* Fetch Docker logins from Consul

## [2.3.0+t.0.3]

* Enhance `SelectedDockerHost` node type with `name_search` and add default to `docker_host_override`
* Implement the functionality in the `select_docker_host` task to query Consul given location id and name search
* Deprecate `location_id` on the `DockerContainerForComponents*` node types
* Change `service_id` to be optional for `DockerContainerForComponents*` node types
* Add deployment id as a tag for registration on the component

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
* Application configuration is now a YAML map to accommodate future blueprint generation
* Update blueprints and cfyhelper.sh 
