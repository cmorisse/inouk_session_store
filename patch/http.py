###################################################################################
#
#    Copyright (c) 2021 Cyril MORISSE (@cmorisse)
#    Copyright (c) 2017-2019 MuK IT GmbH.
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
import random
import timeit
import os

from odoo import http, tools
from odoo.addons.inouk_session_store.store.postgres import PostgresSessionStore
from odoo.addons.inouk_session_store.store.redis import RedisSessionStore
from odoo.http import request
from odoo.tools.func import lazy_property

from ..config import INOUK_SESSION_STORE_REDIS, INOUK_SESSION_STORE_DATABASE, INOUK_SESSION_STORE_DBNAME


_logger = logging.getLogger(__name__)


try:
    import redis
except ImportError:
    if INOUK_SESSION_STORE_REDIS:
        _logger.warning("The Python library redis is not installed.")
    redis = False


def monkey_patch_class(cls):
    def patchr(method):
        method_name = method.__name__
        method._original = getattr(cls, method_name, None)
        setattr(cls, method_name, method)
        return method
    return patchr

def bench_param_access():
    _dd = timeit.timeit(lambda: ENV_VARS['INOUK_SESSION_STORE_DATABASE'], number=100000)
    print("xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx _dict_access=%s", _dd)
    _dv = timeit.timeit(lambda: INOUK_SESSION_STORE_DATABASE, number=100000)
    print("xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx _var_access=%s", _dv)    


@monkey_patch_class(http)
def db_monodb(httprequest=None):
    if INOUK_SESSION_STORE_DATABASE:
        httprequest = httprequest or request.httprequest
        dbs = http.db_list(True, httprequest)
        db_session = httprequest.session.db
        if db_session in dbs:
            return db_session
        if INOUK_SESSION_STORE_DBNAME in dbs:
            dbs.remove(INOUK_SESSION_STORE_DBNAME)
        if len(dbs) == 1:
            return dbs[0]
        return None
    else:
        return db_monodb._original(httprequest)

@monkey_patch_class(http)
def db_filter(dbs, httprequest=None):
    dbs = db_filter._original(dbs, httprequest=httprequest)
    if INOUK_SESSION_STORE_DBNAME in dbs:
        dbs.remove(INOUK_SESSION_STORE_DBNAME)
    return dbs


@monkey_patch_class(http)
def session_gc(session_store):
    if INOUK_SESSION_STORE_DATABASE:
        if random.random() < 0.001:
            session_store.clean()
    elif INOUK_SESSION_STORE_REDIS:
        pass
    else:
        session_gc._original(session_store)


class Root(http.Root):
    @lazy_property
    def session_store(self):
        if INOUK_SESSION_STORE_DATABASE:
            return PostgresSessionStore(session_class=http.OpenERPSession)
        elif INOUK_SESSION_STORE_REDIS:
            return RedisSessionStore(session_class=http.OpenERPSession)
        return super(Root, self).session_store


http.root = Root()
