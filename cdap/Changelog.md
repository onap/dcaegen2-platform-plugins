# Change Log
All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](http://keepachangelog.com/)
and this project adheres to [Semantic Versioning](http://semver.org/).

## [14.0.2]
* Start a tox/pytest unit test suite

## [14.0.1]
* Type file change to move reconfiguration defaults into the type file so each blueprint doesn't need them. 

## [14.0.0]
* Better type speccing in the type file
* Simplify the component naming
* Remove the unused (after two years) location and service-id properties
* Add more demo blueprints and reconfiguration tests

## [13.0.0]
* Support for data router publication. Data router subscription is a problem, see README.
* Fixes `services_calls` to have the same format as streams. This is an API break but users are aware. 

## [12.1.0]
* Support for message router integration. Data router publish to come in next release.  

## [12.0.1]
* Use "localhost" instead of solutioning Consul host. 

## [12.0.0]
* Add in functions for policy to call (execute_workflows) to reconfigure CDAP applications
* Remove "Selected" Nonsense.

FAILURE TO UPDATE

## [10.0.0]
* Update to support broker API 3.X. This is a breaking change, involving the renaming of Node types
* Cut dependencies over to Nexus
