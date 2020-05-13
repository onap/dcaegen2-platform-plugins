# org.onap.ccsdk
# ============LICENSE_START====================================================
# =============================================================================
# Copyright (c) 2017-2018 AT&T Intellectual Property. All rights reserved.
# Copyright (c) 2020 Pantheon.tech. All rights reserved.
# =============================================================================
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#      http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.
# ============LICENSE_END======================================================

"""
PostgreSQL plugin to manage passwords
"""

from __future__ import print_function
import sys
import os
import re
import json
import hashlib
import socket
import traceback
import base64
import binascii
import collections
try:
  from urllib.parse import quote
except ImportError:
  from urllib import quote

from cloudify import ctx
from cloudify.decorators import operation
from cloudify.exceptions import NonRecoverableError
from cloudify.exceptions import RecoverableError

try:
    import psycopg2
except ImportError:
    # FIXME: any users of this plugin installing its dependencies in nonstandard
    # directories should set up PYTHONPATH accordingly, outside the program code
    SYSPATH = sys.path
    sys.path = list(SYSPATH)
    sys.path.append('/usr/lib64/python2.7/site-packages')
    import psycopg2
    sys.path = SYSPATH

from pgaas.logginginterface import debug, info, warn, error


"""
  To set up a cluster:
  - https://$NEXUS/repository/raw/type_files/sshkeyshare/sshkey_types.yaml
  - https://$NEXUS/repository/raw/type_files/pgaas_types.yaml
  sharedsshkey_pgrs:
    type: dcae.nodes.ssh.keypair
  pgaas_cluster:
    type: dcae.nodes.pgaas.cluster
    properties:
      writerfqdn: { get_input: k8s_pgaas_instance_fqdn }
      readerfqdn: { get_input: k8s_pgaas_instance_fqdn }
      # OR:
      # writerfqdn: { concat: [ { get_input: location_prefix }, '-', { get_input: pgaas_cluster_name }, '-write.', { get_input: location_domain } ] }
      # readerfqdn: { concat: [ { get_input: location_prefix }, '-', { get_input: pgaas_cluster_name }, '.', { get_input: location_domain } ] }
    relationships:
      - type: dcae.relationships.pgaas_cluster_uses_sshkeypair
        target: sharedsshkey_pgrs

  To reference an existing cluster:
  - https://$NEXUS/repository/raw/type_files/pgaas_types.yaml
  pgaas_cluster:
    type: dcae.nodes.pgaas.cluster
    properties:
      writerfqdn: { get_input: k8s_pgaas_instance_fqdn }
      # OR: writerfqdn: { concat: [ { get_input: location_prefix }, '-',
      #                             { get_input: pgaas_cluster_name }, '-write.',
      #                             { get_input: location_domain } ] }
      # OR: writerfqdn: { get_property: [ dns_pgrs_rw, fqdn ] }
      use_existing: true

  To initialize an existing server to be managed by pgaas_plugin::
  - https://$NEXUS/repository/raw/type_files/sshkeyshare/sshkey_types.yaml
  - https://$NEXUS/repository/raw/type_files/pgaas_types.yaml
  pgaas_cluster:
    type: dcae.nodes.pgaas.cluster
    properties:
      writerfqdn: { get_input: k8s_pgaas_instance_fqdn }
      readerfqdn: { get_input: k8s_pgaas_instance_fqdn }
      # OR:
      # writerfqdn: { concat: [ { get_input: location_prefix }, '-',
      #                         { get_input: pgaas_cluster_name }, '-write.',
      #                         { get_input: location_domain } ] }
      # readerfqdn: { concat: [ { get_input: location_prefix }, '-',
      #                         { get_input: pgaas_cluster_name }, '.',
      #                         { get_input: location_domain } ] }
      initialpassword: { get_input: currentpassword }
    relationships:
      - type: dcae.relationships.pgaas_cluster_uses_sshkeypair
        target: sharedsshkey_pgrs

  - { get_attribute: [ pgaas_cluster, public ] }
  - { get_attribute: [ pgaas_cluster, base64private ] }
  # - { get_attribute: [ pgaas_cluster, postgrespswd ] }


  To set up a database:
  - http://$NEXUS/raw/type_files/pgaas_types.yaml
  pgaasdbtest:
    type: dcae.nodes.pgaas.database
    properties:
      writerfqdn: { get_input: k8s_pgaas_instance_fqdn }
      # OR: writerfqdn: { concat: [ { get_input: location_prefix }, '-',
      #                             { get_input: pgaas_cluster_name }, '-write.',
      #                             { get_input: location_domain } ] }
      # OR: writerfqdn: { get_property: [ dns_pgrs_rw, fqdn ] }
      name: { get_input: database_name }

  To reference an existing database:
  - http://$NEXUS/raw/type_files/pgaas_types.yaml
  $CLUSTER_$DBNAME:
    type: dcae.nodes.pgaas.database
    properties:
      writerfqdn: { get_input: k8s_pgaas_instance_fqdn }
      # OR: writerfqdn: { concat: [ { get_input: location_prefix }, '-',
      #                             { get_input: pgaas_cluster_name }, '-write.',
      #                             { get_input: location_domain } ] }
      # OR: writerfqdn: { get_property: [ dns_pgrs_rw, fqdn ] }
      name: { get_input: database_name }
      use_existing: true

  $CLUSTER_$DBNAME_admin_host:
    description: Hostname for $CLUSTER $DBNAME database
    value: { get_attribute: [ $CLUSTER_$DBNAME, admin, host ] }
  $CLUSTER_$DBNAME_admin_user:
    description: Admin Username for $CLUSTER $DBNAME database
    value: { get_attribute: [ $CLUSTER_$DBNAME, admin, user ] }
  $CLUSTER_$DBNAME_admin_password:
    description: Admin Password for $CLUSTER $DBNAME database
    value: { get_attribute: [ $CLUSTER_$DBNAME, admin, password ] }
  $CLUSTER_$DBNAME_user_host:
    description: Hostname for $CLUSTER $DBNAME database
    value: { get_attribute: [ $CLUSTER_$DBNAME, user, host ] }
  $CLUSTER_$DBNAME_user_user:
    description: User Username for $CLUSTER $DBNAME database
    value: { get_attribute: [ $CLUSTER_$DBNAME, user, user ] }
  $CLUSTER_$DBNAME_user_password:
    description: User Password for $CLUSTER $DBNAME database
    value: { get_attribute: [ $CLUSTER_$DBNAME, user, password ] }
  $CLUSTER_$DBNAME_viewer_host:
    description: Hostname for $CLUSTER $DBNAME database
    value: { get_attribute: [ $CLUSTER_$DBNAME, viewer, host ] }
  $CLUSTER_$DBNAME_viewer_user:
    description: Viewer Username for $CLUSTER $DBNAME database
    value: { get_attribute: [ $CLUSTER_$DBNAME, viewer, user ] }
  $CLUSTER_$DBNAME_viewer_password:
    description: Viewer Password for $CLUSTER $DBNAME database
    value: { get_attribute: [ $CLUSTER_$DBNAME, viewer, password ] }

"""

OPT_MANAGER_RESOURCES_PGAAS = "/opt/manager/resources/pgaas"

# pylint: disable=invalid-name
def setOptManagerResources(o): # pylint: disable=global-statement
  """
  Overrides the default locations of /opt/managers/resources
  """
  # pylint: disable=global-statement
  global OPT_MANAGER_RESOURCES_PGAAS
  OPT_MANAGER_RESOURCES_PGAAS = "{}/pgaas".format(o)

def safestr(s):
  """
  returns a safely printable version of the string
  """
  return quote(str(s), '')

def raiseRecoverableError(msg):
  """
  Print a warning message and raise a RecoverableError exception.
  This is a handy endpoint to add other extended debugging calls.
  """
  warn(msg)
  raise RecoverableError(msg)

def raiseNonRecoverableError(msg):
  """
  Print an error message and raise a NonRecoverableError exception.
  This is a handy endpoint to add other extended debugging calls.
  """
  error(msg)
  raise NonRecoverableError(msg)

def dbexecute(crx, cmd, args=None):
  """
  executes the SQL statement
  Prints the entire command for debugging purposes
  """
  debug("executing {}".format(cmd))
  crx.execute(cmd, args)


def dbexecute_trunc_print(crx, cmd, args=None):
  """
  executes the SQL statement.
  Will print only the first 30 characters in the command
  Use this function if you are executing an SQL cmd with a password
  """
  debug("executing {}".format(cmd[:30]))
  crx.execute(cmd, args)


def waithp(host, port):
  """
  do a test connection to a host and port
  """
  debug("waithp({0},{1})".format(safestr(host), safestr(port)))
  sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
  try:
    sock.connect((host, int(port)))
  except: # pylint: disable=bare-except
    a, b, c = sys.exc_info()
    traceback.print_exception(a, b, c)
    sock.close()
    raiseRecoverableError('Server at {0}:{1} is not ready'.format(safestr(host), safestr(port)))
  sock.close()

def doconn(desc):
  """
  open an SQL connection to the PG server
  """
  debug("doconn({},{},{})".format(desc['host'], desc['user'], desc['database']))
  # debug("doconn({},{},{},{})".format(desc['host'], desc['user'], desc['database'], desc['password']))
  ret = psycopg2.connect(**desc)
  ret.autocommit = True
  return ret

def hostportion(hostport):
  """
  return the host portion of a fqdn:port or IPv4:port or [IPv6]:port
  """
  ipv4re = re.match(r"^([^:]+)(:(\d+))?", hostport)
  ipv6re = re.match(r"^[[]([^]]+)[]](:(\d+))?", hostport)
  if ipv4re:
    return ipv4re.group(1)
  if ipv6re:
    return ipv6re.group(1)
  raiseNonRecoverableError("invalid hostport: {}".format(hostport))

def portportion(hostport):
  """
  Return the port portion of a fqdn:port or IPv4:port or [IPv6]:port.
  If port is not present, return 5432.
  """
  ipv6re = re.match(r"^[[]([^]]+)[]](:(\d+))?", hostport)
  ipv4re = re.match(r"^([^:]+)(:(\d+))?", hostport)
  if ipv4re:
    return ipv4re.group(3) if ipv4re.group(3) else '5432'
  if ipv6re:
    return ipv6re.group(3) if ipv6re.group(3) else '5432'
  raiseNonRecoverableError("invalid hostport: {}".format(hostport))

def rootdesc(data, dbname, initialpassword=None):
  """
  return the postgres connection information
  """
  debug("rootdesc(..data..,{0})".format(safestr(dbname)))
  # pylint: disable=bad-continuation
  return {
    'database': dbname,
    'host': hostportion(data['rw']),
    'port': portportion(data['rw']),
    'user': 'postgres',
    'password': initialpassword if initialpassword else getpass(data, 'postgres', data['rw'], 'postgres')
  }

def rootconn(data, dbname='postgres', initialpassword=None):
  """
  connect to a given server as postgres,
  connecting to the specified database
  """
  debug("rootconn(..data..,{0})".format(safestr(dbname)))
  return doconn(rootdesc(data, dbname, initialpassword))

def onedesc(data, dbname, role, access):
  """
  return the connection information for a given user and dbname on a cluster
  """
  user = '{0}_{1}'.format(dbname, role)
  # pylint: disable=bad-continuation
  return {
    'database': dbname,
    'host': hostportion(data[access]),
    'port': portportion(data[access]),
    'user': user,
    'password': getpass(data, user, data['rw'], dbname)
  }

def dbdescs(data, dbname):
  """
  return the entire set of information for a specific server/database
  """
  # pylint: disable=bad-continuation
  return {
    'admin': onedesc(data, dbname, 'admin', 'rw'),
    'user': onedesc(data, dbname, 'user', 'rw'),
    'viewer': onedesc(data, dbname, 'viewer', 'ro')
  }

def getpass(data, ident, hostport, dbname):
  """
  generate the password for a given user on a specific server
  """
  m = hashlib.sha256()
  m.update(ident.encode())

  # mix in the seed (the last line) for that database, if one exists
  hostport = hostport.lower()
  dbname = dbname.lower()
  hostPortDbname = '{0}/{1}:{2}'.format(OPT_MANAGER_RESOURCES_PGAAS, hostport, dbname)
  try:
    lastLine = ''
    with open(hostPortDbname, "r") as fp:
      for line in fp:
        lastLine = line
    m.update(lastLine.encode())
  except IOError:
    pass

  m.update(base64.b64decode(data['data']))
  return m.hexdigest()

def find_related_nodes(reltype, inst=None):
  """
  extract the related_nodes information from the context
  for a specific relationship
  """
  if inst is None:
    inst = ctx.instance
  ret = []
  for rel in inst.relationships:
    if reltype in rel.type_hierarchy:
      ret.append(rel.target)
  return ret

def chkfqdn(fqdn):
  """
  verify that a FQDN is valid
  """
  if fqdn is None:
    return False
  hp = hostportion(fqdn)
  # not needed right now: pp = portportion(fqdn)
  # TODO need to augment this for IPv6 addresses
  return re.match('^[a-zA-Z0-9_-]+(\\.[a-zA-Z0-9_-]+)+$', hp) is not None

def chkdbname(dbname):
  """
  verify that a database name is valid
  """
  ret = re.match('[a-zA-Z][a-zA-Z0-9]{0,43}', dbname) is not None and dbname != 'postgres'
  if not ret:
    warn("Invalid dbname: {0}".format(safestr(dbname)))
  return ret

def get_valid_domains():
  """
  Return a list of the valid names, suitable for inclusion in an error message.
  """
  msg = ''
  import glob
  validDomains = []
  for f in glob.glob('{}/*'.format(OPT_MANAGER_RESOURCES_PGAAS)):
    try:
      with open(f, "r") as fp:
        try:
          tmpdata = json.load(fp)
          if 'pubkey' in tmpdata:
            validDomains.append(os.path.basename(f))
        except: # pylint: disable=bare-except
          pass
    except: # pylint: disable=bare-except
      pass
  if len(validDomains) == 0:
    msg += '\nNo valid PostgreSQL cluster information was found'
  else:
    msg += '\nThese are the valid PostgreSQL cluster domains found on this manager:'
    for v in validDomains:
      msg += '\n\t"{}"'.format(v)
  return msg

def get_existing_clusterinfo(wfqdn, rfqdn, related):
  """
  Retrieve all of the information specific to an existing cluster.
  """
  if rfqdn != '':
    raiseNonRecoverableError('Read-only FQDN must not be specified when using an existing cluster, fqdn={0}'.format(safestr(rfqdn)))
  if len(related) != 0:
    raiseNonRecoverableError('Cluster SSH keypair must not be specified when using an existing cluster')
  try:
    fn = '{0}/{1}'.format(OPT_MANAGER_RESOURCES_PGAAS, wfqdn.lower())
    with open(fn, 'r') as f:
      data = json.load(f)
      data['rw'] = wfqdn
      return data
  except Exception as e: # pylint: disable=broad-except
    warn("Error: {0}".format(e))
    msg = 'Cluster must be deployed when using an existing cluster.\nCheck your domain name: fqdn={0}\nerr={1}'.format(safestr(wfqdn), e)
    if not os.path.isdir(OPT_MANAGER_RESOURCES_PGAAS):
      msg += '\nThe directory {} does not exist. No PostgreSQL clusters have been deployed on this manager.'.format(OPT_MANAGER_RESOURCES_PGAAS)
    else:
      msg += get_valid_domains()
    # warn("Stack: {0}".format(traceback.format_exc()))
    raiseNonRecoverableError(msg)

def getclusterinfo(wfqdn, reuse, rfqdn, initialpassword, related):
  """
  Retrieve all of the information specific to a cluster.
  if reuse, retrieve it
  else create and store it
  """
  # debug("getclusterinfo({}, {}, {}, {}, ..related..)".format(safestr(wfqdn), safestr(reuse), safestr(rfqdn), safestr(initialpassword)))
  debug("getclusterinfo({}, {}, {}, ..related..)".format(safestr(wfqdn), safestr(reuse), safestr(rfqdn)))
  if not chkfqdn(wfqdn):
    raiseNonRecoverableError('Invalid FQDN specified for admin/read-write access, fqdn={0}'.format(safestr(wfqdn)))
  if reuse:
    return get_existing_clusterinfo(wfqdn, rfqdn, related)

  if rfqdn == '':
    rfqdn = wfqdn
  elif not chkfqdn(rfqdn):
    raiseNonRecoverableError('Invalid FQDN specified for read-only access, fqdn={0}'.format(safestr(rfqdn)))
  if len(related) != 1:
    raiseNonRecoverableError('Cluster SSH keypair must be specified using a dcae.relationships.pgaas_cluster_uses_sshkeypair ' +
                             'relationship to a dcae.nodes.sshkeypair node')
  data = {'ro': rfqdn, 'pubkey': related[0].instance.runtime_properties['public'],
          'data': related[0].instance.runtime_properties['base64private'], 'hash': 'sha256'}
  os.umask(0o77)
  try:
    os.makedirs('{0}'.format(OPT_MANAGER_RESOURCES_PGAAS))
  except: # pylint: disable=bare-except
    pass
  try:
    with open('{0}/{1}'.format(OPT_MANAGER_RESOURCES_PGAAS, wfqdn.lower()), 'w') as f:
      f.write(json.dumps(data))
  except Exception as e: # pylint: disable=broad-except
    warn("Error: {0}".format(e))
    warn("Stack: {0}".format(traceback.format_exc()))
    raiseNonRecoverableError('Cannot write cluster information to {0}: fqdn={1}, err={2}'.format(OPT_MANAGER_RESOURCES_PGAAS, safestr(wfqdn), e))
  data['rw'] = wfqdn
  if initialpassword:
    with rootconn(data, initialpassword=initialpassword) as conn:
      crr = conn.cursor()
      dbexecute_trunc_print(crr, "ALTER USER postgres WITH PASSWORD %s", (getpass(data, 'postgres', wfqdn, 'postgres'),))
      crr.close()
  return data

@operation
def add_pgaas_cluster(**kwargs): # pylint: disable=unused-argument
  """
  dcae.nodes.pgaas.cluster:
  Record key generation data for cluster
  """
  try:
    warn("add_pgaas_cluster() invoked")
    data = getclusterinfo(ctx.node.properties['writerfqdn'],
                          ctx.node.properties['use_existing'],
                          ctx.node.properties['readerfqdn'],
                          ctx.node.properties['initialpassword'],
                          find_related_nodes('dcae.relationships.pgaas_cluster_uses_sshkeypair'))
    ctx.instance.runtime_properties['public'] = data['pubkey']
    ctx.instance.runtime_properties['base64private'] = data['data']
    ctx.instance.runtime_properties['postgrespswd'] = getpass(data, 'postgres', ctx.node.properties['writerfqdn'], 'postgres')
    warn('All done')
  except Exception as e: # pylint: disable=broad-except
    ctx.logger.warn("Error: {0}".format(e))
    ctx.logger.warn("Stack: {0}".format(traceback.format_exc()))
    raise e

@operation
def rm_pgaas_cluster(**kwargs): # pylint: disable=unused-argument
  """
  dcae.nodes.pgaas.cluster:
  Remove key generation data for cluster
  """
  try:
    warn("rm_pgaas_cluster()")
    wfqdn = ctx.node.properties['writerfqdn']
    if chkfqdn(wfqdn) and not ctx.node.properties['use_existing']:
      os.remove('{0}/{1}'.format(OPT_MANAGER_RESOURCES_PGAAS, wfqdn))
    warn('All done')
  except Exception as e: # pylint: disable=broad-except
    ctx.logger.warn("Error: {0}".format(e))
    ctx.logger.warn("Stack: {0}".format(traceback.format_exc()))
    raise e

def dbgetinfo(refctx):
  """
  Get the data associated with a database.
  Make sure the connection exists.
  """
  wfqdn = refctx.node.properties['writerfqdn']
  related = find_related_nodes('dcae.relationships.database_runson_pgaas_cluster', refctx.instance)
  if wfqdn == '':
    if len(related) != 1:
      raiseNonRecoverableError('Database Cluster must be specified using exactly one dcae.relationships.database_runson_pgaas_cluster relationship ' +
                               'to a dcae.nodes.pgaas.cluster node when writerfqdn is not specified')
    wfqdn = related[0].node.properties['writerfqdn']
  return dbgetinfo_for_update(wfqdn)

def dbgetinfo_for_update(wfqdn):
  """
  Get the data associated with a database.
  Make sure the connection exists.
  """

  if not chkfqdn(wfqdn):
    raiseNonRecoverableError('Invalid FQDN specified for admin/read-write access, fqdn={0}'.format(safestr(wfqdn)))
  ret = getclusterinfo(wfqdn, True, '', '', [])
  waithp(hostportion(wfqdn), portportion(wfqdn))
  return ret

@operation
def create_database(**kwargs):
  """
  dcae.nodes.pgaas.database:
  Create a database on a cluster
  """
  try:
    debug("create_database() invoked")
    dbname = ctx.node.properties['name']
    warn("create_database({0})".format(safestr(dbname)))
    if not chkdbname(dbname):
      raiseNonRecoverableError('Unacceptable or missing database name: {0}'.format(safestr(dbname)))
    debug('create_database(): dbname checked out')
    dbinfo = dbgetinfo(ctx)
    debug('Got db server info')
    descs = dbdescs(dbinfo, dbname)
    ctx.instance.runtime_properties['admin'] = descs['admin']
    ctx.instance.runtime_properties['user'] = descs['user']
    ctx.instance.runtime_properties['viewer'] = descs['viewer']
    with rootconn(dbinfo) as conn:
      crx = conn.cursor()
      dbexecute(crx, 'SELECT datname FROM pg_database WHERE datistemplate = false')
      existingdbs = [x[0] for x in crx]
      if ctx.node.properties['use_existing']:
        if dbname not in existingdbs:
          raiseNonRecoverableError('use_existing specified but database does not exist, dbname={0}'.format(safestr(dbname)))
        return
      dbexecute(crx, 'SELECT rolname FROM pg_roles')
      existingroles = [x[0] for x in crx]
      admu = descs['admin']['user']
      usru = descs['user']['user']
      vwru = descs['viewer']['user']
      cusr = '{0}_common_user_role'.format(dbname)
      cvwr = '{0}_common_viewer_role'.format(dbname)
      schm = '{0}_db_common'.format(dbname)
      if admu not in existingroles:
        dbexecute_trunc_print(crx, 'CREATE USER {0} WITH PASSWORD %s'.format(admu), (descs['admin']['password'],))
      if usru not in existingroles:
        dbexecute_trunc_print(crx, 'CREATE USER {0} WITH PASSWORD %s'.format(usru), (descs['user']['password'],))
      if vwru not in existingroles:
        dbexecute_trunc_print(crx, 'CREATE USER {0} WITH PASSWORD %s'.format(vwru), (descs['viewer']['password'],))
      if cusr not in existingroles:
        dbexecute(crx, 'CREATE ROLE {0}'.format(cusr))
      if cvwr not in existingroles:
        dbexecute(crx, 'CREATE ROLE {0}'.format(cvwr))
      if dbname not in existingdbs:
        dbexecute(crx, 'CREATE DATABASE {0} WITH OWNER {1}'.format(dbname, admu))
      crx.close()
    with rootconn(dbinfo, dbname) as dbconn:
      crz = dbconn.cursor()
      for r in [cusr, cvwr, usru, vwru]:
        dbexecute(crz, 'REVOKE ALL ON DATABASE {0} FROM {1}'.format(dbname, r))
      dbexecute(crz, 'GRANT {0} TO {1}'.format(cvwr, cusr))
      dbexecute(crz, 'GRANT {0} TO {1}'.format(cusr, admu))
      dbexecute(crz, 'GRANT CONNECT ON DATABASE {0} TO {1}'.format(dbname, cvwr))
      dbexecute(crz, 'CREATE SCHEMA IF NOT EXISTS {0} AUTHORIZATION {1}'.format(schm, admu))
      for r in [admu, cusr, cvwr, usru, vwru]:
        dbexecute(crz, 'ALTER ROLE {0} IN DATABASE {1} SET search_path = public, {2}'.format(r, dbname, schm))
      dbexecute(crz, 'GRANT USAGE ON SCHEMA {0} to {1}'.format(schm, cvwr))
      dbexecute(crz, 'GRANT CREATE ON SCHEMA {0} to {1}'.format(schm, admu))
      dbexecute(crz, 'ALTER DEFAULT PRIVILEGES FOR ROLE {0} GRANT SELECT ON TABLES TO {1}'.format(admu, cvwr))
      dbexecute(crz, 'ALTER DEFAULT PRIVILEGES FOR ROLE {0} GRANT INSERT, UPDATE, DELETE, TRUNCATE ON TABLES TO {1}'.format(admu, cusr))
      dbexecute(crz, 'ALTER DEFAULT PRIVILEGES FOR ROLE {0} GRANT USAGE, SELECT, UPDATE ON SEQUENCES TO {1}'.format(admu, cusr))
      dbexecute(crz, 'GRANT TEMP ON DATABASE {0} TO {1}'.format(dbname, cusr))
      dbexecute(crz, 'GRANT {0} to {1}'.format(cusr, usru))
      dbexecute(crz, 'GRANT {0} to {1}'.format(cvwr, vwru))
      crz.close()
    warn('All done')
  except Exception as e: # pylint: disable=broad-except
    ctx.logger.warn("Error: {0}".format(e))
    ctx.logger.warn("Stack: {0}".format(traceback.format_exc()))
    raise e

@operation
def delete_database(**kwargs): # pylint: disable=unused-argument
  """
  dcae.nodes.pgaas.database:
  Delete a database from a cluster
  """
  try:
    debug("delete_database() invoked")
    dbname = ctx.node.properties['name']
    warn("delete_database({0})".format(safestr(dbname)))
    if not chkdbname(dbname):
      return
    debug('delete_database(): dbname checked out')
    if ctx.node.properties['use_existing']:
      return
    debug('delete_database(): !use_existing')
    dbinfo = dbgetinfo(ctx)
    debug('Got db server info')
    with rootconn(dbinfo) as conn:
      crx = conn.cursor()
      admu = ctx.instance.runtime_properties['admin']['user']
      usru = ctx.instance.runtime_properties['user']['user']
      vwru = ctx.instance.runtime_properties['viewer']['user']
      cusr = '{0}_common_user_role'.format(dbname)
      cvwr = '{0}_common_viewer_role'.format(dbname)
      dbexecute(crx, 'DROP DATABASE IF EXISTS {0}'.format(dbname))
      for r in [usru, vwru, admu, cusr, cvwr]:
        dbexecute(crx, 'DROP ROLE IF EXISTS {0}'.format(r))
    warn('All gone')
  except Exception as e: # pylint: disable=broad-except
    ctx.logger.warn("Error: {0}".format(e))
    ctx.logger.warn("Stack: {0}".format(traceback.format_exc()))
    raise e

#############################################################
# function: update_database                                 #
# Purpose: Called as a workflow to change the database      #
#          passwords for all the users                      #
#                                                           #
# Invoked via:                                              #
# cfy executions start -d <deployment-id> update_db_passwd  #
#                                                           #
# Assumptions:                                              #
# 1) pgaas_types.yaml must define a work flow e.g.          #
#    workflows:                                             #
#      update_db_passwd :                                   #
#        mapping : pgaas.pgaas.pgaas_plugin.update_database #
# 2) DB Blueprint: node_template must have properties:      #
#     writerfqdn & name (of DB)                             #
#############################################################
# pylint: disable=unused-argument
@operation
def update_database(refctx, **kwargs):
  """
  dcae.nodes.pgaas.database:
  Update the password for a database from a cluster
  refctx is auto injected into the function when called as a workflow
  """
  try:
    debug("update_database() invoked")

    ################################################
    # Verify refctx contains the <nodes> attribute.   #
    # The workflow context might not be consistent #
    # across different cloudify versions           #
    ################################################
    if not hasattr(refctx, 'nodes'):
      raiseNonRecoverableError('workflow context does not contain attribute=<nodes>. dir(refctx)={}'.format(dir(refctx)))

    ############################################
    # Verify that refctx.nodes is iterable        #
    ############################################
    if not isinstance(refctx.nodes, collections.Iterable):
      raiseNonRecoverableError("refctx.nodes is not an iterable. Type={}".format(type(refctx.nodes)))

    ctx_node = None
    ##############################################
    # Iterate through the nodes until we find    #
    # one with the properties we are looking for #
    ##############################################
    for i in refctx.nodes:

      ############################################
      # Safeguard: If a given node doesn't have  #
      #            properties then skip it.      #
      # Don't cause an exception since the nodes #
      # entry we are searching might still exist #
      ############################################
      if not hasattr(i, 'properties'):
        warn('Encountered a ctx node that does not have attr=<properties>. dir={}'.format(dir(i)))
        continue

      debug("ctx node has the following Properties: {}".format(list(i.properties.keys())))

      if ('name' in i.properties) and ('writerfqdn' in i.properties):
        ctx_node = i
        break


    ###############################################
    # If none of the nodes have properties:       #
    # <name> and <writerfqdn> then fatal error    #
    ###############################################
    if not ctx_node:
      raiseNonRecoverableError('Either <name> or <writerfqdn> is not found in refctx.nodes.properties.')

    debug("name is {}".format(ctx_node.properties['name']))
    debug("host is {}".format(ctx_node.properties['writerfqdn']))

    dbname = ctx_node.properties['name']
    debug("update_database({0})".format(safestr(dbname)))

    ###########################
    # dbname must be valid    #
    ###########################
    if not chkdbname(dbname):
      raiseNonRecoverableError('dbname is null')


    hostport = ctx_node.properties['writerfqdn']
    debug('update_database(): wfqdn={}'.format(hostport))
    dbinfo = dbgetinfo_for_update(hostport)

    #debug('Got db server info={}'.format(dbinfo))

    hostPortDbname = '{0}/{1}:{2}'.format(OPT_MANAGER_RESOURCES_PGAAS, hostport.lower(), dbname.lower())

    debug('update_database(): hostPortDbname={}'.format(hostPortDbname))
    try:
      appended = False
      with open(hostPortDbname, "a") as fp:
        with open("/dev/urandom", "rb") as rp:
          b = rp.read(16)
          print(binascii.hexlify(b).decode('utf-8'), file=fp)
          appended = True
      if not appended:
        ctx.logger.warn("Error: the password for {} {} was not successfully changed".format(hostport, dbname))
    except Exception as e: # pylint: disable=broad-except
      ctx.logger.warn("Error: {0}".format(e))
      ctx.logger.warn("Stack: {0}".format(traceback.format_exc()))
      raise e

    descs = dbdescs(dbinfo, dbname)

    ##########################################
    # Verify we have expected keys           #
    # <admin>, <user>, and <viewer> as well  #
    # as "sub-key" <user>                    #
    ##########################################

    if not isinstance(descs, dict):
      raiseNonRecoverableError('db descs has unexpected type=<{}> was expected type dict'.format(type(descs)))

    for key in ("admin", "user", "viewer"):
      if key not in descs:
        raiseNonRecoverableError('db descs does not contain key=<{}>. Keys found for descs are: {}'.format(key, list(descs.keys())))
      if 'user' not in descs[key]:
        raiseNonRecoverableError('db descs[{}] does not contain key=<user>. Keys found for descs[{}] are: {}'.format(key, key, list(descs[key].keys())))


    with rootconn(dbinfo) as conn:
      crx = conn.cursor()

      admu = descs['admin']['user']
      usru = descs['user']['user']
      vwru = descs['viewer']['user']

      for r in [usru, vwru, admu]:
        dbexecute_trunc_print(crx, "ALTER USER {} WITH PASSWORD '{}'".format(r, getpass(dbinfo, r, hostport, dbname)))
        #debug("user={} password={}".format(r, getpass(dbinfo, r, hostport, dbname)))

    warn('All users updated for database {}'.format(dbname))
  except Exception as e: # pylint: disable=broad-except
    ctx.logger.warn("Error: {0}".format(e))
    ctx.logger.warn("Stack: {0}".format(traceback.format_exc()))
    raise e
