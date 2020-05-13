<!--
============LICENSE_START=======================================================
org.onap.ccsdk
================================================================================
Copyright (c) 2017 AT&T Intellectual Property. All rights reserved.
================================================================================
Licensed under the Apache License, Version 2.0 (the "License");
you may not use this file except in compliance with the License.
You may obtain a copy of the License at

     http://www.apache.org/licenses/LICENSE-2.0

Unless required by applicable law or agreed to in writing, software
distributed under the License is distributed on an "AS IS" BASIS,
WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
See the License for the specific language governing permissions and
limitations under the License.
============LICENSE_END=========================================================
-->

# sshkeyshare plugin
Cloudify plugin for creating ssh key pairs on the fly
# Description
The sshkeyshare Cloudify plugin creates an ssh key pair that can be used,
by VMs or other containers spun up by a Cloudify blueprint, for establishing
connections, among them.  The blue print can, for example, provide the
private key to one VM and the public one to another, as part of their
initial configuration, to allow the one with the private key to
automatically connect to the other one, to run commands.
# Plugin Requirements
* Python versions
 * 2.7.x

Note: These requirements apply to the VM where Cloudify Manager itself runs.

Note: Cloudify Manager, itself, requires Pythong 2.7.x (and CentOS 7).

# Types
## ccsdk.nodes.ssh.keypair
**Derived From:** cloudify.nodes.Root

**Properties:**
This type has no properties

**Mapped Operations:**
* `cloudify.interfaces.lifecycle.create` Creates a new ssh keypair
using ssh-keygen

**Attributes:**
* `public` A string containing the public key of the newly created
keypair.
* `base64private` A single line base-64 encoded representation of
the content of the private key file for the newly created keypair.

# Relationships
This plugin does not define or use any relationships
