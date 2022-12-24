###################################################################################
#
#    Copyright (c) 2017-2019 MuK IT GmbH.
#
#    This file is part of MuK Session Store
#    (see https://mukit.at).
#
#    This program is free software: you can redistribute it and/or modify
#    it under the terms of the GNU Lesser General Public License as published by
#    the Free Software Foundation, either version 3 of the License, or
#    (at your option) any later version.
#
#    This program is distributed in the hope that it will be useful,
#    but WITHOUT ANY WARRANTY; without even the implied warranty of
#    MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
#    GNU Lesser General Public License for more details.
#
#    You should have received a copy of the GNU Lesser General Public License
#    along with this program. If not, see <http://www.gnu.org/licenses/>.
#
###################################################################################

{
    "name": "Inouk Session Store",
    "summary": """Allow to store sessions in either PostgreSQL or Redis (Soon). This is a fork of the Muk Session Store Addon from Muk It.""",
    "version": "13.0.1.0.0",
    "category": "Extra Tools",
    "license": "LGPL-3",
    "website": "https://github.com/cmorisse/inouk_session_store.git",
    "author": "MuK IT, Cyril MORISSE",
    "contributors": ["Mathias Markl <mathias.markl@mukit.at>", "Cyril MORISSE <cmorisse@boxes3.net>"],
    "depends": ["inouk_core"],
    "images": [],
    "application": False,
    "installable": True,
    "post_load": "_patch_system",
}
