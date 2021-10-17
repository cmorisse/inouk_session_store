###################################################################################
#
#    Copyright (c) 2021 Cyril MORISSE (@cmorisse)
#
#    This file is part of Inouk Session Store
#    (see https://gitub.com/cmorisse/inouk_session_store).
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

import logging
import timeit
import os


_logger = logging.getLogger("InoukSessionStore")

ENV_VARS = None
INOUK_SESSION_STORE_DATABASE = None  # Allowed values: 'undefined', 'postgres' or 'redis'
INOUK_SESSION_STORE_REDIS = None
INOUK_SESSION_STORE_DBNAME = None
INOUK_SESSION_STORE_DBTABLE = None
INOUK_SESSION_STORE_DEBUG = False

def load_env_vars():
    global ENV_VARS
    global INOUK_SESSION_STORE_DATABASE
    global INOUK_SESSION_STORE_REDIS
    global INOUK_SESSION_STORE_DBNAME
    global INOUK_SESSION_STORE_DBTABLE    
    global INOUK_SESSION_STORE_DEBUG    
    if ENV_VARS is None:
        INOUK_SESSION_STORE_DATABASE = os.environ.get('INOUK_SESSION_STORE', 'undefined').lower()=='postgres'
        INOUK_SESSION_STORE_REDIS = os.environ.get('INOUK_SESSION_STORE', 'undefined').lower()=='redis'
        INOUK_SESSION_STORE_DBNAME = os.environ.get('INOUK_SESSION_STORE_DBNAME', 'inouk_session_store').lower()
        INOUK_SESSION_STORE_DBTABLE = os.environ.get('INOUK_SESSION_STORE_DBTABLE', 'odoo_sessions').lower()
        INOUK_SESSION_STORE_DEBUG = os.environ.get('INOUK_SESSION_STORE_DEBUG', "0").lower() in ['yes', 'true', '1', 'y']

        ENV_VARS = {
            'INOUK_SESSION_STORE_DATABASE': INOUK_SESSION_STORE_DATABASE,
            'INOUK_SESSION_STORE_REDIS': INOUK_SESSION_STORE_REDIS,
            'INOUK_SESSION_STORE_DBNAME': INOUK_SESSION_STORE_DBNAME,
            'INOUK_SESSION_STORE_DBTABLE': INOUK_SESSION_STORE_DBTABLE,
            'INOUK_SESSION_STORE_DEBUG': INOUK_SESSION_STORE_DEBUG
        }
        print(ENV_VARS)
    _logger.info("ENV VARs loaded.")
    return ENV_VARS

if ENV_VARS is None:
    load_env_vars()
