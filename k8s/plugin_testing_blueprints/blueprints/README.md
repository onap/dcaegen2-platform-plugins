# Blueprints for testing the DCAE Kubernetes plugin
The blueprints in this directory are designed as test cases for the DCAE
Kubernetes Cloudify plugin (`k8splugin`).  Each blueprint tests a single
feature, or small set of features, supported by the plugin.

The testing strategy here is simple and not very automated.  Deploying a DCAE
component using a Cloudify blueprint typically has a number of effects (creating a
Kubernetes deployment, creating a Kubernetes service, populating configuration information
into Consul, mounting certain volumes on a container, and so forth).  For now at least, we use a
manual process to verify that deployment has had the expected effects:
- we use `kubectl` to checkthat the expected Kubernetes artifacts are created
-  we look into Consul to see that the appropriateconfiguration information has been populated (including configuration information that comes
from DMaaP and policy where the blueprint calls for it)
- we `kubectl exec` into the container to verify that the expected environment variables have been set and the expected volumes are mounted and have the correct content

All of the blueprints deploy the `nginx` image from the public Docker Hub.  The blueprints
will generally deploy the `nginx` Web server so that it serves the default Web page on port 80
of the container and on a NodePort if the blueprint specifies an external port address.
Some of the blueprints set up TLS.  The expected result is that the appropriate directories
will be created and will hold the TLS artifacts.   We don't actually configure `nginx` to use
TLS.