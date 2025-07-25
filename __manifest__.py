# -*- coding: utf-8 -*-
{
    'name': 'Inouk Session Store',
    'summary': 'Allow to store sessions in either PostgreSQL or Redis (Soon). This is a fork of the Muk Session Store Addon from Muk It.',
    'version': '1.0.0',
    'category': 'Extra Tools',
    'license': 'LGPL-3',
    'website': 'https://github.com/cmorisse/inouk_session_store.git',
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
