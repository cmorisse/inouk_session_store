===================
Inouk Session Store
===================

Warning: This is a fork of Muk It - Odoo Session Store.

By default Odoo stores web client (werkzeug) sessions in the file system. This prevent to scale Odoo 
on several instances.

This addon allows to store sessions either in a PostgreSQL Database or Redis making it 
possible to scale Odoo by adding instances.

Requirements
============

The requirements are only required if Redis is used as the session store.

Redis
-----

A interface to the Redis key-value store for Python. To install Redis please follow the
`instructions <https://github.com/andymccurdy/redis-py>`_ or install the library via pip.

``pip install redis``

Installation
============

To install this module, you need to:

Download the module and add it to your Odoo addons folder. Afterward, log on to
your Odoo server and go to the Apps menu. Trigger the debug mode and update the
list by clicking on the "Update Apps List" link. Now install the module by
clicking on the install button.

Upgrade
=======

To upgrade this module, you need to:

Download the module and add it to your Odoo addons folder. Restart the server
and log on to your Odoo server. Select the Apps menu and upgrade the module by
clicking on the upgrade button.


Configuration
=============

Since this module need to be activated even if no database is selected it should
be loaded right at the server start. This can be done by editing the configuration
file or passing a load parameter to the start script.

Parameter: ``--load=web,inouk_session_store``

Or in odoo config file: ``server_wide_modules = base,web,inouk_session_store```


Addon options
-------------

Once added, this module's configuration is done exclusively using these ENVIRONMENT VARIABLES.

INOUK_SESSION_STORE = 'postgresql' or 'redis'


PostgreSQL options
__________________

If INOUK_SESSION_STORE is postgresql, 2 more options are available:

    * INOUK_SESSION_STORE_DBNAME ; The name of the database used to store sessions. Default value is `inouk_session_store`.

    * INOUK_SESSION_STORE_DBTABLE ; The name of the table used to store sessions. Default value is `odoo_sessions`.


Redis options
_____________

Redis support is not implemented yet.

* session_store_prefix
* session_store_host
* session_store_port
* session_store_dbindex
* session_store_pass
* session_store_ssl
* session_store_ssl_cert_reqs

Redis usage
___________

After setting the parameters, the session store is used automatically.

In order to use ssl, which is a requirement of some databases, session_store_ssl
should be set to True and session_store_ssl_cert_reqs should be set to 'required'
except in the case where the server certificate does not match the host name.

e.g.
# Server has a proper certificate
session_store_ssl=True
session_store_ssl_cert_reqs=required

# Server does not have a proper certificate (AWS possibly)
session_store_ssl=True
session_store_ssl_cert_reqs=None

For more information please see the redis python module documentation


Other common options
____________________

INOUK_SESSION_STORE_DEBUG is reserved for future use.



Credit
======

Contributors
------------

* Mathias Markl <mathias.markl@mukit.at>
* Cyril MORISSE <cmorisse@boxes3.net>

Images
------

Some pictures are based on or inspired by the icon set of Font Awesome:

* `Font Awesome <https://fontawesome.com>`_


Projects
--------

Parts of the module are inspired by:

* `PSQL Session Store <https://github.com/it-projects-llc/misc-addons>`_


Author & Maintainer
-------------------

This module is maintained by Cyril MORISSE <cmorisse@boxes3.net>
