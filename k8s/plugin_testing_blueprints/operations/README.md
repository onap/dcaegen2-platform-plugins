# Parameter Files for Testing Operations
The k8s plugin supports some operations beyond just installation and uninstallation:
- `scale`: change the number of replicas of component
- `update_image`: change the Docker image used for the component
- `policy_update`: update a component's configuration in Consul and notify the component of the change

The files in this directory contain parameters for testing the additional operations.
The specific values in the files are tied to values in the blueprints in the `../blueprints` directory.

## Invoking an operation
Invoking the operations here involves running the Cloudify `execute_operation` workflow.

   `cfy executions start -p `_/path/to/operation_file_`  -d  `_name_of_cloudify_deployment_` execute_operation`

