import sshkeyshare.keyshare_plugin
from cloudify.mocks import MockCloudifyContext
from cloudify.state import current_ctx
from cloudify import ctx

def test_generate():
  mock_ctx = MockCloudifyContext(node_id='test_node_id', node_name='test_node_name', properties={})
  try:
    current_ctx.set(mock_ctx)
    sshkeyshare.keyshare_plugin.generate()
    pub = ctx.instance.runtime_properties['public']
    pvt64 = ctx.instance.runtime_properties['base64private']
  finally:
    current_ctx.clear()
