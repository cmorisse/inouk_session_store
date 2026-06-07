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

import os
import re
import time
import base64
import functools
import logging
import pickle

from hashlib import sha512

from odoo.tools import config
from odoo.tools._vendor import sessions
from odoo.service import security, model as service_model
# Soft-rotation contract constants, kept in sync with odoo.http.
from odoo.http import STORED_SESSION_BYTES, SESSION_DELETION_TIMER


_logger = logging.getLogger(__name__)

try:
    import redis
except ImportError:
    pass

SESSION_TIMEOUT = 60 * 60 * 24 * 7

# Mirrors odoo.http (see store/postgres.py for the rationale): new sids are
# 84-char url-safe base64 so the first STORED_SESSION_BYTES chars form a stable
# identifier across soft rotations; legacy 40-char sha1 hex sids stay accepted.
_base64_urlsafe_re = re.compile(r'^[A-Za-z0-9_-]{84}$')
_session_identifier_re = re.compile(r'^[A-Za-z0-9_-]{%s}$' % STORED_SESSION_BYTES)
_legacy_sha1_re = re.compile(r'^[0-9a-f]{40}$')


def retry_redis(func):
    @functools.wraps(func)
    def wrapper(self, *args, **kwargs):
        for attempts in range(1, 6):
            try:
                return func(self, *args, **kwargs)
            except redis.ConnectionError as error:
                _logger.warn("SessionStore connection failed! (%s/5)" % attempts)
                if attempts >= 5:
                    raise error

    return wrapper


class RedisSessionStore(sessions.SessionStore):
    def __init__(self, *args, **kwargs):
        raise Exception("Redis Session Store is not supported yet.")
        super(RedisSessionStore, self).__init__(*args, **kwargs)
        self.prefix = config.get("session_store_prefix", "")
        self.server = redis.Redis(
            host=config.get("session_store_host", "localhost"),
            port=int(config.get("session_store_port", 6379)),
            db=int(config.get("session_store_dbindex", 1)),
            password=config.get("session_store_pass", None),
            ssl=config.get("session_store_ssl", False),
            ssl_cert_reqs=config.get("session_store_ssl_cert_reqs", None),
        )

    def _encode_session_key(self, key):
        return key.encode("utf-8") if isinstance(key, str) else key

    def _get_session_key(self, sid):
        return self._encode_session_key(self.prefix + sid)

    @retry_redis
    def save(self, session, ttl=SESSION_TIMEOUT):
        key = self._get_session_key(session.sid)
        payload = pickle.dumps(dict(session), pickle.HIGHEST_PROTOCOL)
        self.server.setex(name=key, value=payload, time=ttl)

    @retry_redis
    def delete(self, session):
        self.server.delete(self._get_session_key(session.sid))

    def rotate(self, session, env, soft=False):
        # See store/postgres.py::rotate. Soft rotation keeps the 42-char
        # identifier prefix stable and retains the old key only for the grace
        # window (here via a short Redis TTL, so it self-expires even if
        # delete_old_sessions never runs).
        if soft:
            static = session.sid[:STORED_SESSION_BYTES]
            recent_session = self.get(session.sid)
            if 'next_sid' in recent_session:
                session.sid = recent_session['next_sid']
                return
            next_sid = static + self.generate_key()[STORED_SESSION_BYTES:]
            session['next_sid'] = next_sid
            session['deletion_time'] = time.time() + SESSION_DELETION_TIMER
            self.save(session, ttl=SESSION_DELETION_TIMER)
            session['gc_previous_sessions'] = True
            session.sid = next_sid
            del session['deletion_time']
            del session['next_sid']
        else:
            self.delete(session)
            session.sid = self.generate_key()
        if session.uid:
            assert env, "saving this session requires an environment"
            session.session_token = security.compute_session_token(session, env)
        session.should_rotate = False
        session['create_time'] = time.time()
        self.save(session)

    @retry_redis
    def get(self, sid):
        if not self.is_valid_key(sid):
            return self.new()
        key = self._get_session_key(sid)
        payload = self.server.get(key)
        if payload:
            self.server.setex(name=key, value=payload, time=SESSION_TIMEOUT)
            return self.session_class(pickle.loads(payload), sid, False)
        else:
            return self.session_class({}, sid, False)

    def generate_key(self, salt=None):
        # 84-char url-safe base64 key (see store/postgres.py).
        key = str(time.time()).encode() + os.urandom(64)
        hash_key = sha512(key).digest()[:-1]  # prevent base64 padding
        return base64.urlsafe_b64encode(hash_key).decode('utf-8')

    def is_valid_key(self, key):
        # Accept both new 84-char base64 keys and legacy 40-char sha1 hex keys.
        return bool(_base64_urlsafe_re.match(key) or _legacy_sha1_re.match(key))

    def delete_old_sessions(self, session):
        # Per-request GC hook (security.check_session). The previous key set by
        # a soft rotation already self-expires via its short TTL; once the grace
        # window has elapsed we also reap it explicitly and clear the flag.
        if 'gc_previous_sessions' in session:
            if session['create_time'] + SESSION_DELETION_TIMER < time.time():
                self.delete_from_identifiers([session.sid[:STORED_SESSION_BYTES]])
                del session['gc_previous_sessions']
                self.save(session)

    def vacuum(self, max_lifetime=SESSION_TIMEOUT):
        # No-op: Redis expires session keys natively through the setex TTL.
        return

    def clean(self):
        self.vacuum()

    @retry_redis
    def get_missing_session_identifiers(self, identifiers):
        # Used by res.device(.log): return the identifiers (sid[:42] prefixes)
        # that have no live session key.
        identifiers = set(identifiers)
        missing = set()
        for identifier in identifiers:
            pattern = self._encode_session_key(self.prefix + identifier + '*')
            if next(iter(self.server.scan_iter(match=pattern, count=1)), None) is None:
                missing.add(identifier)
        return missing

    @retry_redis
    def delete_from_identifiers(self, identifiers):
        # Delete every session key whose sid starts with one of the given
        # 42-char identifiers (device revocation and soft-rotation cleanup).
        keys = []
        for identifier in identifiers:
            if not _session_identifier_re.match(identifier):
                continue
            pattern = self._encode_session_key(self.prefix + identifier + '*')
            keys.extend(self.server.scan_iter(match=pattern))
        if keys:
            self.server.delete(*keys)

