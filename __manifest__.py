# -*- coding: utf-8 -*-
{
    'name': 'Inouk Session Store',
    'summary': 'Allow to store sessions in either PostgreSQL or Redis (Soon). This is a fork of the Muk Session Store Addon from Muk It.',
    'description': """
Stores Odoo web sessions in PostgreSQL (Redis planned) so several instances can serve
the same users, and serves ``/inouk_health_check``, a session-less JSON probe that reports
whether this server writes to a primary or a standby, plus the versions the installed
modules choose to publish.
""",
    'version': '1.1.0',
    'category': 'Extra Tools',
    'license': 'LGPL-3',
    'website': 'https://gitlab.com/cmorisse/inouk_session_store',
    'author': 'MuK IT, Cyril MORISSE',
    'contributors': [
        'Mathias Markl <mathias.markl@mukit.at>',
        'Cyril MORISSE <cmorisse@boxes3.net>'
    ],
    'depends': ['inouk_core'],
    'images': [],
    'application': False,
    'installable': True,
    'post_load': '_patch_system'
}
