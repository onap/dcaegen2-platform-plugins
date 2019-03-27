#supporting policy_model_id for clamp

 - Adding a new node type extended from dcae.node.policy, so it is backward comatible with policy_id and 
   compatible with newly introduced policy_model_id

 ## Usage

import the clamppolicy-node-type.yaml into your blueprint to use the clamp.nodes.type node

```yaml
imports:
    - https://YOUR_NEXUS_RAW_SERVER/type_files/clamppolicy/1.0.0/clamppolicy-node-type.yaml
```

provide the value for policy_model_id property

```yaml
node_templates:
...
  policy_model:
    type: clamp.nodes.policy
    properties:
        policy_model_id: { get_input: policy_model_id }
```

Then the clamppolicyplugin will bring the latest policy model id to the clamp.nodes.policy node 
during the install workflow of cloudify.
