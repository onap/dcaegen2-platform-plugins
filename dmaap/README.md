## Cloudify DMaaP Plugin
Cloudify plugin for creating and managing DMaaP Data Router feeds and subscriptions and
DMaaP Message Router topics.   The plugin uses the DMaaP Bus Controller API.

### Plugin Support for DMaaP Data Router
#### Plugin Types for DMaaP Data Router
The Cloudify type definitions for DMaaP Data Router nodes and relationships
are defined in [`dmaap.yaml`](./dmaap.yaml).

There are four node types for DMaaP Data Router:

- `ccsdk.nodes.Feed`: This type represents a feed that does not yet
exist and that should be created when the install workflow is
run against a blueprint that contains a node of this type.

Property|Type|Required?|Description                           |
--------|----|---------|---------------------------------------
feed_name|string|no|a name that identifies the feed (plugin will generate if absent)
feed_version|string|no|version number for the feed (feed_name + feed_version uniquely identify the feed in DR)
feed_description|string|no|human-readable description of the feed
aspr_classification|string|no|AT&T ASPR classification of the feed


- `ccsdk.nodes.ExistingFeed`: This type represents a feed that
already exists.  Nodes of this type are placed in a blueprint so
that other nodes in the blueprint can be set up as publishers or
subscribers to the feed. The table below shows the properties that a node
of this type may have.

Property|Type|Required?|Description
--------|----|---------|----------------------------------------
feed_id|string|no|Feed identifier assigned by DMaaP when the feed was created
feed_name|string|no|a name that identifies the feed

- `ccsdk.nodes.ExternalTargetFeed`:  This type represents a feed created in an external DMaaP
environment (i.e., an environment that the plugin cannot access to make provisioning requests, such as
a shared corporate system).  Nodes of this type are placed in a blueprint so that other feed nodes of
type `ccsdk.nodes.Feed` or `ccsdk.nodes.ExistingFeed` can be set up to "bridge" to external feeds by
publishing data to the external feeds.  The table below shows the properties that a node of this type
may have.

Property|Type|Required?|Description
--------|----|---------|----------------------------------------
url|string|yes|The publish URL of the external feed.
username|string|yes|The username to be used when delivering to the external feed
userpw|string|yes|The password to be used when delivering to the external feed

_Note: These properties are usually obtained by manually creating a feed in the external
DMaaP DR system and then creating a publisher for that feed._

- `ccsdk.nodes.ExternalSourceFeed`:  This type represents a feed created in an external DMaaP
environment (i.e., an environment that the plugin cannot access to makes provisioning requests, such as
a shared corporate system).  Nodes of this type are place in a blueprint so that they can be set up to
"bridge" to other feed nodes of type `ccsdk.nodes.Feed` or `ccsdk.nodes.ExistingFeed`.  This type
has no node properties, but when a bridge is set up, the url, username, and password are attached to the
node as runtime_properties, using the name of the target feed node as the top-level key.

There are five relationship types for DMaaP Data Router:

- `ccsdk.relationships.publish_files`,  used to
indicate that the relationship's source node sends is a publisher to the
Data Router feed represented by the relationship's target node.
- `ccsdk.relationships.subscribe_to_files`, used to
indicate that the relationship's source node is a subscriber to the
Data Router feed represented by the relationship's target node.
- `ccsdk.relationships.bridges_to`, used to indicate that the relationship's source
node (a `ccsdk.nodes.Feed` or `ccsdk.nodes.ExistingFeed`) should be set up
to forward data ("bridge") to the relationship's target feed (another `ccsdk.nodes.Feed` or
`ccsdk.nodes.ExistingFeed`).
- `ccsdk.relationships.bridges_to_external`, used to indicate that the relationship's source
node (a `ccsdk.nodes.Feed` or `ccsdk.nodes.ExistingFeed`) should be set up
to forward data  ("bridge") to the relationship's target node (a feed in an external DMaaP system,
represented by a `ccsdk.nodes.ExternalTargetFeed` node).
- `ccsdk.relationships.bridges_from_external_to_internal`, used to indicate the the relationship's source
node (a feed in an external DMaaP system, represented by a `ccsdk.nodes.ExternalSourceFeed` node) should be set up to forward date ("bridge")
to the relationship's target node (an internal ONAP feed, represented by a `ccsdk.nodes.Feed` or `ccsdk.nodes.ExistingFeed` node).

The plugin code implements the lifecycle operations needed to create and
delete feeds and to add and remove publishers and subscribers.  It also implements
the operations needed to set up bridging between feeds.

#### Interaction with Other Plugins
When creating a new feed or processing a reference to an existing feed,
the plugin operates independently of other plugins.

When processing a `ccsdk.relationships.publish_files` relationship or a
`ccsdk.relationships.subscribe_to_files` relationship, this plugin needs
to obtain data from the source node and, in the case of `publish_files`, provide
data to the source node.  Certain conventions are therefore needed for
passing data between this plugin and the plugins responsible for the source
nodes in these relationships.  In Cloudify, the mechanism for
sharing data among plugins is the `ctx.instance.runtime_properties` dictionary
associated with each node.

A given source node may have relationships with several feeds.  For example, an ONAP DCAE
data collector might publish two different types of data to two different feeds.  An ONAP DCAE
analytics module might subscribe to one feed to get input for its processing and
publish its results to a different feed.   When this DMaaP plugin and the plugin for the
source node exchange information, they need to do in a way that lets them distinguish
among different feeds.   We do this through a simple convention:  for each source node
to feed relationship, the source node plugin will create a property in the source node's
`runtime_properties` dictionary.  The name of the property will be the same as the
name of the target node of the relationship.  For instance, if a node has a
`publishes_files` relationship with a target node named `feed00`, then the plugin that's
responsible for managing the source node with create an entry in the source node's
`runtime_properties` dictionary named `feed00`.  This entry itself will be a dictionary.

The content of this data exchange dictionary depends on whether the source node is a
publisher (i.e., the relationship is `publish_files`) or a subscriber (i.e., the
relationship is `subscribe_to_files`).

For the `publish_files` relationship, the data exchange dictionary has the following
properties:

Property|Set by|Description
--------|------|------------------------------------------------
location|source node plugin|the DMaaP location for the publisher, used to set up routing
publish_url|DMaaP plugin|the URL to which the publisher makes Data Router publish requests
log_url|DMaaP plugin|the URL from which log data for the feed can be obtained
username|DMaaP plugin|the username (generated by the DMaaP plugin) the publisher uses to authenticate to Data Router
password|DMaaP plugin|the password (generated by the DMaaP plugin) the publisher uses to authenticate to Data Router

For the `subscribe_to_files` relationship, the data exchange dictionary has the following
properties:

Property|Set by|Description
--------|------|------------------------------------------------
location|source node plugin|the DMaaP location for the subscriber, used to set up routing
delivery_url|source node plugin|the URL to which the Data Router should deliver files
username|source node plugin|the username Data Router uses to authenticate to the subscriber when delivering files
password|source node plugin|the username Data Router uses to authenticate to the subscriber when delivering file

### Plugin Support for DMaaP Message Router
#### Plugin Types for DMaaP Message Router
The Cloudify type definitions for DMaaP Message Router nodes and relationships
are defined in [`dmaap.yaml`](./dmaap.yaml).

There are two node types for DMaaP Message Router:

- `ccsdk.nodes.Topic`: This type represents a topic that does not yet
exist and that should be created when the install workflow is
run against a blueprint that contains a node of this type.

Property|Type|Required?|Description
--------|----|---------|---------------------------------------
topic_name|string|no|a name that uniquely identifies the feed (plugin will generate if absent or is empty string or contain only whitespace)
topic_description|string|no|human-readable description of the feed
txenable|boolean|no|flag indicating whether transactions are enabled for this topic
replication_case|string|no|type of replication required for the topic (defaults to no replication)
global_mr_url|string|no|Global MR host name for replication to a global MR instance

Note: In order to set up topics, a user should be familiar with message router and how it is configured,
and this README is not the place to explain the details of message router. Here are a couple of pieces of
information that might be helpful.
Currently, the allowed values for `replication_case` are:

- `REPLICATION_NONE`
- `REPLICATION_EDGE_TO_CENTRAL`
- `REPLICATION_EDGE_TO_CENTRAL_TO_GLOBAL`
- `REPLICATION_CENTRAL_TO_EDGE`
- `REPLICATION_CENTRAL_TO_GLOBAL`
- `REPLICATION_GLOBAL_TO_CENTRAL`
- `REPLICATION_GLOBAL_TO_CENTRAL_TO_EDGE`

The `global_mr_url` is actually a host name, not a full URL.  It points to a host in a global message router
cluster.  (A 'global' message router cluster is one that's not part of ONAP.)

- `ccsdk.nodes.ExistingTopic`: This type represents a topic that
already exists.  Nodes of this type are placed in a blueprint so
that other nodes in the blueprint can be set up as publishers or
subscribers to the topic. The table below shows the properties that a node
of this type may have.

Property|Type|Required?|Description
--------|----|---------|----------------------------------------
fqtn|string|no|fully-qualified topic name for the topic
topic_name|string|no|a name that identifies the topic

#### Interaction with Other Plugins
When creating a new topic or processing a reference to an existing topic,
the plugin operates independently of other plugins.

When processing a `ccsdk.relationships.publish_events` relationship or a
`ccsdk.relationships.subscribe_to_events` relationship, this plugin needs
to obtain data from  and provide data to the source node. Certain conventions are therefore needed for
passing data between this plugin and the plugins responsible for the source
nodes in these relationships.  In Cloudify, the mechanism for
sharing data among plugins is the `ctx.instance.runtime_properties` dictionary
associated with each node.

A given source node may have relationships with several topics.  For example, an ONAP DCAE
analytics module might subscribe to one topic to get input for its processing and
publish its results to a different topic.   When this DMaaP plugin and the plugin for the
source node exchange information, they need to do in a way that lets them distinguish
among different feeds.   We do this through a simple convention:  for each source node
to topic relationship, the source node plugin will create a property in the source node's
`runtime_properties` dictionary.  The name of the property will be the same as the
name of the target node of the relationship.  For instance, if a node has a
`publishes_events` relationship with a target node named `topic00`, then the plugin that's
responsible for managing the source node with create an entry in the source node's
`runtime_properties` dictionary named `topic00`.  This entry itself will be a dictionary.

For both types of relationship, the data exchange dictionary has the following
properties:

Property|Set by|Description
--------|------|------------------------------------------------
location|source node plugin|the DMaaP location for the publisher or subscriber, used to set up routing
client_role|source node plugin|the AAF client role that's requesting publish or subscribe access to the topic
topic_url|DMaaP plugin|the URL for accessing the topic to publish or receive events

### Interaction with Consul configuration store
In addition to storing the results of DMaaP Data Router and DMaaP Message Router provisioning operations in `runtime_properties`,
the DMaaP plugin also stores these results into the ONAP configuration store, which resides in a
[Consul key-value store](https://www.consul.io/).  This allows DMaaP clients (components that act as publishers, subscribers, or both)
to retrieve their DMaaP configuration information from Consul, rather than having the plugin that deploys the client directly
configure the client using data in `runtime_properties`.

The `runtime_properties` for a client must contain a property called `service_component_name`.  If this property is not present,
the plugin will raise a NonRecoverableError and cause the installation to fail.

If `service_component_name` is present, then the plugin will use a Consul key consisting of the value
of `service_component_name` prepended to the fixed string `:dmaap`.   For example, if the `service_component_name`
is `client123`, the plugin will use `client123:dmaap` as the key for storing DMaaP information into Consul.
Information for all of the feeds and topics for a client are stored under the same key.

The value stored is a nested JSON object.  At the top level of the object are properties representing each topic or feed
for which the component is a publisher or subscriber.  The name of the property is the node name of the target feed or topic.
The value of the property is another JSON object that corresponds to the dictionary that the plugin created in
`runtime_properties` corresponding to the target feed or topic.  Note that the information in Consul includes
all of the properties for the feed or topic, those set by the source node plugin as well as those set by the DMaaP plugin.

Examples:

Data Router publisher, target feed `feed00`:
```
{
  "feed00": {
    "username": "rC9QR51I",
    "log_url": "https://dmaap.example.com/feedlog/972",
    "publish_url": "https://dmaap.example.com/publish/972",
    "location": "loc00",
    "password": "QOQeUh5KLR",
    "publisher_id": "972.360gm"
  }
}
```

Data Router subscriber, target feed `feed01`:
```
{
  "feed01": {
    "username": "drdeliver",
    "password": "1loveDataR0uter",
    "location": "loc00",
    "delivery_url": "https://example.com/whatever",
    "subscriber_id": "1550"
  }
}
```

Message Router publisher to `topic00`, subscriber to `topic01`.  Note how each topic
appears as a top-level property in the object.
```
{
  "topic00": {
    "topic_url": "https://dmaap.example.com:3905/events/org.onap.ccsdk.dmaap.FTL2.outboundx",
    "client_role": "org.onap.ccsdk.member",
    "location": "loc00",
    "client_id": "1494621774522"
  },
  "topic01": {
    "topic_url": "https://dmaap.example.com:3905/events/org.onap.ccsdk.dmaap.FTL2.inboundx",
    "client_role": "org.onap.ccsdk.member",
    "location": "loc00",
    "client_id": "1494621778627"
  }
}
```

### Packaging and installing
The DMaaP plugin is meant to be used as a [Cloudify managed plugin](http://docs.getcloudify.org/3.4.0/plugins/using-plugins/). Managed plugins
are packaged using [`wagon`](https://github.com/cloudify-cosmo/wagon).

To package this plugin, executing the following command in the top-level directory of this plugin, from a Python environment in which `wagon` has been installed:
```
wagon create -s . -r -o /path/to/directory/for/wagon/output
```
Once the wagon file is built, it can be uploaded to a Cloudify Manager host using the `cfy plugins upload` command described in the documentation above.

Managed plugins can also be loaded at the time a Cloudify Manager host is installed, via the installation blueprint and inputs file.  We expect that this plugin will
be loaded at Cloudify Manager installation time, and that `cfy plugins upload` will be used only for delivering patches between releases.

### Configuration
The plugin needs to be configured with certain parameters needed to access the DMaaP Bus Controller.  In keeping with the ONAP architecture, this information is
stored in Consul.

The plugin finds the address and port of the DMaaP Bus Controller using the Consul service discovery facility.  The plugin expects the Bus Controller to be
registered under the name `dmaap_bus_controller`.

Additional parameters come from the `dmaap` key in the Cloudify Manager's Consul configuration, which is stored in the Consul KV store under the key name
'cloudify_manager'.  The table below lists the properties in the configuration:

Property|Type|Required?|Default|Description
--------|----|---------|-------|--------------------------------
`username`|string|Yes|(none)|The username for logging into DMaaP Bus Controller
`password`|string|Yes|(none)|The password for logging into DMaaP Bus Controller
`owner`|string|Yes|(none)|The name to be used as the owner for entities created by the plugin
`protocol`|string|No|`https`|The protocol (URL scheme) used to access the DMaaP bus controller (`http` or `https`)
`path`|string|No|`webapi`|The path to the root of the DMaaP Bus Controller API endpoint

Here is an example of a Cloudify Manager configuration object showing only the `dmaap` key:
```
{
  "dmaap": {
    "username": "dmaap.client@ccsdkorch.onap.org",
    "password": "guessmeifyoucan"
    "owner": "ccsdkorc"
  },

  (other configuration here)

}
```
