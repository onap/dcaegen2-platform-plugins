# PGaaS Plugin
Cloudify PGaaS plugin description and configuraiton
# Description
The PGaaS plugin allows users to deploy PostgreSQL application databases, and retrieve access credentials for such databases, as part of a Cloudify blueprint.
# Plugin Requirements
* Python versions
 * 2.7.x
* System dependencies
 * psycopg2

Note: These requirements apply to the VM where Cloudify Manager itself runs.

Note: The psycopg2 requirement is met by running "yum install python-psycopg2" on the Cloudify Manager VM.

Note: Cloudify Manager, itself, requires Python 2.7.x (and Centos 7).

# Types
## dcae.nodes.pgaas.cluster
**Derived From:** cloudify.nodes.Root

**Properties:**

* `writerfqdn` (required string) The FQDN used for read-write access to the
cluster containing the postgres database instance.  This is used to identify
and access a particular database instance and to record information about
that instance on Cloudify Manager.
* `use_existing` (optional boolean default=false)  This is used to reference
a database instance, in one blueprint, that was deployed in a different one.
If it is `true`, then the `readerfqdn` property must not be set and this node
must not have any `dcae.relationships.pgaas_cluster_uses_sshkeypair`
relationships.  If it is `false`, then this node must have exactly one
`dcae.relationships.pgaas_cluster_uses_sshkeypair` relationship.
* `readerfqdn` (optional string default=value of `writerfqdn`)  The FQDN used for read-only access to the cluster containing the postgres database instance, if different than the FQDN used for read-write access.  This will be used by viewer roles.

**Mapped Operations:**

* `cloudify.interfaces.lifecycle.create` validates and records information about the cluster on the Cloudify Manager server in /opt/manager/resources/pgaas/`writerfqdn`.
* `cloudify.interfaces.lifecycle.delete` deletes previously recorded information from the Cloudify Manager server.

Note: When `use_existing` is `true`, the create operation validates but does not record, and delete does nothing.  Delete also does nothing when validation has failed.

**Attributes:**
This type has no runtime attributes

## dcae.nodes.pgaas.database
**Derived From:** cloudify.nodes.Root

**Properties:**
* `name` (required string) The name of the application database, in postgres.  This name is also used to create the names of the roles used to access the database, and the schema made available to users of the database.
* `use_existing` (optional boolean default=false) This is used to reference an application database, in one blueprint, that was deployed in a different one.  If true, and this node has a dcae.relationships.database_runson_pgaas_cluster relationship, the dcae.nodes.pgaas.cluster node that is the target of that relationship must also have it's `use_existing` property set to true.
* `writerfqdn` (optional string)  This can be used as an alternative to specifying the cluster, for the application database, with a dcae.relationships.database_runson_pgaas_cluster relationship to a dcae.nodes.pgaas.cluster node.  Exactly one of the two options must be used.  The relationship method must be used if this blueprint is deploying both the cluster and the application database on the cluster.

**Mapped Operations:**

* `cloudify.interfaces.lifecycle.create` creates the application database, and various roles for admin/user/viewer access to it.
* `cloudify.interfaces.lifecycle.delete` deletes the application database and roles

Note: When `use_existing` is true, create and delete do not create or delete the application database or associated roles.  Create still sets runtime attributes (see below).

**Attributes:**

* `admin` a dict containing access information for adminstrative access to the application database.
* `user` a dict containing access information for user access to the application database.
* `viewer` a dict containing access information for read-only access to the application database.

The keys in the access information dicts are as follows:

* `database` the name of the application database.
* `host` the appropriate FQDN for accessing the application database, (writerfqdn or readerfqdn, based on the type of access).
* `user` the user role for accessing the database.
* `password` the password corresponding to the user role.

# Relationships
## dcae.relationships.pgaas_cluster_uses_sshkeypair
**Description:** A relationship for binding a dcae.nodes.pgaas.cluster node to the dcae.nodes.ssh.keypair used by the cluster to initialize the database access password for the postgres role.  The password for the postgres role is expected to be the hex representation of the MD5 hash of 'postgres' and the contents of the id_rsa (private key) file for the ssh keypair.  A dcae.nodes.pgaas.cluster node must have such a relationship if and only if it's use_existing property is false.
## dcae.relationships.dcae.relationships.database_runson_pgaas_cluster
**Description:** A relationship for binding a dcae.nodes.pgaas.database node to the dcae.nodes.pgaas.cluster node that contains the application database.  A dcae.nodes.pgaas.database node must have either such a relationship or a writerfqdn property.  The writerfqdn property cannot be used if the cluster is created in the same blueprint as the application database.
## dcae.relationships.application_uses_pgaas_database
**Description:** A relationship for binding a node that needs application database access information to the dcae.nodes.pgaas.database node for that application database.
