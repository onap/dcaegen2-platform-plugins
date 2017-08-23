# relationships-cloudify

This repo contains Cloudify artifacts to support custom functionality in processing relationships between nodes.

* `component_connected_to` - Used to connect service component nodes together
* `component_contained_in` - Used to place service component nodes on their proper container host or cluster

## `component_connected_to`

This Cloudify relationship is used to collect the relationship information of all the target nodes of a source node and to provide this information to the source node application.  Currently, this information is provided by being stored in the platform Consul instance under the key `<source node's name>:rel`.

Each target node is expected to provide its own name (name used for service registration) to the source node.  These target names are passed as a runtime property of the target node context under the key `service_component_name`.

### Special features

#### `target_name_override`

The preconfigure operation uses the task function `add_relationship` which has an *optional* input parameter `target_name_override`.  The target name is passed into the source node's relationship information that is used by the source node underlying application to connect to the target node underlying application.  If not used, the default behavior is to expect the target name to come from the target node as a runtime property under the key `service_component_name`.

##### When should you use this?

When you know the target node does not populate `service_component_name` into its runtime properties.

##### Usage example

Here is an example of how you would use the `target_name_override` input parameter in a blueprint:

```yaml
node_templates:

  some-source:
    type: dcae.nodes.rework.DockerContainer
    properties:
        service_component_type:
            'laika'
        service_id:
            { get_input: service_id }
        location_id:
            'rework-central'
        application_config:
            { get_input: some-source-config }
        image:
            'dcae-rework/laika:0.4.0'
    relationships:
      - type: dcae.relationships.component_connected_to
        target: some-target
        target_interfaces:
            cloudify.interfaces.relationship_lifecycle:
                preconfigure:
                    inputs:
                        target_name_override:
                            'some-target'
```

