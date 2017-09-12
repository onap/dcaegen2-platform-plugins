# dcae-policy plugin and node-type
- python-package dcaepolicyplugin to be used in cloudify plugins to retrieve the policy from policy-handler

---

## dcaepolicy node type [dcaepolicy-node-type.yaml](./dcaepolicy-node-type.yaml)
- node type for dcae.nodes.policy

---

## Usage

import the dcaepolicy-node-type.yaml into your blueprint to use the dcae.nodes.type node

```yaml
imports:
    - https://YOUR_NEXUS_RAW_SERVER/type_files/dcaepolicy/1.0.0/node-type.yaml
```

provide the value for policy_id property

```yaml
node_templates:
...
  host_capacity_policy:
    type: dcae.nodes.policy
    properties:
        policy_id: { get_input: host_capacity_policy_id }
```

Then the dcaepolicyplugin will bring the latest policy to the dcae.nodes.policy node during the install workflow of cloudify.
