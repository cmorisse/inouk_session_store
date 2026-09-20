# Inouk Session Store

Warning: This is a fork of Muk It - Odoo Session Store.

By default Odoo stores web client (werkzeug) sessions in the file system. This prevent to scale Odoo
on several instances.

This addon allows to store sessions either in a PostgreSQL Database or Redis making it
possible to scale Odoo by adding instances.

## Requirements

The requirements are only required if Redis is used as the session store.

### Redis

A interface to the Redis key-value store for Python. To install Redis please follow the
[instructions](https://github.com/andymccurdy/redis-py) or install the library via pip.

```
pip install redis
```

## Installation

To install this module, you need to:

Download the module and add it to your Odoo addons folder. Afterward, log on to
your Odoo server and go to the Apps menu. Trigger the debug mode and update the
list by clicking on the "Update Apps List" link. Now install the module by
clicking on the install button.

## Upgrade

To upgrade this module, you need to:

Download the module and add it to your Odoo addons folder. Restart the server
and log on to your Odoo server. Select the Apps menu and upgrade the module by
clicking on the upgrade button.

## Configuration

Since this module need to be activated even if no database is selected it should
be loaded right at the server start. This can be done by editing the configuration
file or passing a load parameter to the start script.

Parameter: `--load=web,inouk_session_store`

Or in odoo config file: `server_wide_modules = base,web,inouk_session_store`

### Addon options

Once added, this module's configuration is done exclusively using these ENVIRONMENT VARIABLES.

INOUK_SESSION_STORE = 'postgresql' or 'redis'

#### PostgreSQL options

If INOUK_SESSION_STORE = postgresql, 3 more options are available:

- INOUK_SESSION_STORE_DBNAME ; The name of the database used to store sessions. Default value is `inouk_session_store`.
- INOUK_SESSION_STORE_DBTABLE ; The name of the table used to store sessions. Default value is `inouk_odoo_sessions`.
- INOUK_SESSION_STORE_SAMEDB ; Set to True to allow to store session in the current database. Default value is `False`.
  Requires odoo to be launched with --database parameter.

#### Redis options

Redis support is not implemented yet.

- session_store_prefix
- session_store_host
- session_store_port
- session_store_dbindex
- session_store_pass
- session_store_ssl
- session_store_ssl_cert_reqs

#### Redis usage

After setting the parameters, the session store is used automatically.

In order to use ssl, which is a requirement of some databases, session_store_ssl
should be set to True and session_store_ssl_cert_reqs should be set to 'required'
except in the case where the server certificate does not match the host name.

e.g.

```
# Server has a proper certificate
session_store_ssl=True
session_store_ssl_cert_reqs=required

# Server does not have a proper certificate (AWS possibly)
session_store_ssl=True
session_store_ssl_cert_reqs=None
```

For more information please see the redis python module documentation

#### Other common options

INOUK_SESSION_STORE_DEBUG is reserved for future use.

## Health check endpoint

The addon serves `GET /inouk_health_check`, a JSON probe meant for a load balancer, a
supervision agent or a deployment script.

Because the addon is loaded through `server_wide_modules`, the route answers on every
database, installed or not. It is `auth='none'` and session-less (`save_session=False`):
a probe needs no credentials and is handed no `session_id` cookie, so polling it every
few seconds leaves nothing behind.

The answer is a JSON object:

```json
{
  "replication_status": "cluster_is_primary",
  "versions": [{"name": "muppy", "version": "18.89.0"}]
}
```

### `replication_status`

Whether the PostgreSQL node this server writes to is a primary or a standby:

- `cluster_is_primary` — the server writes to a primary and accepts writes;
- `cluster_is_standby` — the server writes to a node in recovery, so it serves reads only.

The route declares `readonly=False` on purpose. The question is about the node THIS
server writes to: with `db_replica_host` configured, the default read-only transaction of
an `auth='none'` route would run the `pg_is_in_recovery()` query on the replica, and a
healthy primary would report itself as a standby.

### `versions`

A list of the versions the installed modules choose to publish. Each entry is an object
carrying at least `name` and `version`, so a contributor can add a field later without
breaking a reader.

The list is empty by default — this addon publishes nothing about itself. A module that
wants to appear inherits the controller and extends the list; Odoo composes every
subclass of a controller into a single class, so several modules contribute without
knowing about each other:

```python
from odoo.addons.inouk_session_store.controllers.health_check import InoukHealthCheck


class MyHealthCheck(InoukHealthCheck):

    def _health_check_versions(self):
        versions = super()._health_check_versions()
        versions.append({'name': 'my_app', 'version': my_version()})
        return versions
```

The route is `auth='none'`, which means anyone who can reach the server reads this list.
Publish only what may be public.

## Credit

### Contributors

- Mathias Markl <mathias.markl@mukit.at>
- Cyril MORISSE <cmorisse@boxes3.net>

### Images

Some pictures are based on or inspired by the icon set of Font Awesome:

- [Font Awesome](https://fontawesome.com)

### Projects

Parts of the module are inspired by:

- [PSQL Session Store](https://github.com/it-projects-llc/misc-addons)

### Author & Maintainer

This module is maintained by Cyril MORISSE <cmorisse@boxes3.net>
