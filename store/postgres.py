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

import os
import re
import time
import base64
import pickle
import logging
import psycopg2
import functools

from hashlib import sha512
from contextlib import closing
from contextlib import contextmanager
from datetime import datetime, date

#from werkzeug.contrib.sessions import SessionStore
from odoo.tools._vendor import sessions

from odoo.sql_db import db_connect
from odoo.tools import config
from odoo.service import security, model as service_model
# Soft-rotation contract constants, kept in sync with odoo.http.
from odoo.http import STORED_SESSION_BYTES, SESSION_DELETION_TIMER


from ..config import INOUK_SESSION_STORE_DATABASE, INOUK_SESSION_STORE_DBNAME, INOUK_SESSION_STORE_DBTABLE

# Mirrors odoo.http: new sids are 84-char url-safe base64 so that the first
# STORED_SESSION_BYTES (42) chars form a stable identifier usable across soft
# rotations (csrf token, res.device.log). Legacy sids were 40-char sha1 hex;
# we keep accepting them so existing cookies survive the upgrade.
_base64_urlsafe_re = re.compile(r'^[A-Za-z0-9_-]{84}$')
_session_identifier_re = re.compile(r'^[A-Za-z0-9_-]{%s}$' % STORED_SESSION_BYTES)
_legacy_sha1_re = re.compile(r'^[0-9a-f]{40}$')

_logger = logging.getLogger(__name__)


def retry_database(func):
    @functools.wraps(func)
    def wrapper(self, *args, **kwargs):
        for attempts in range(1, 6):
            try:
                return func(self, *args, **kwargs)
            except psycopg2.InterfaceError as error:
                _logger.warn("SessionStore connection failed! (%s/5)" % attempts)
                if attempts >= 5:
                    raise error

    return wrapper


class PostgresSessionStore(sessions.SessionStore):
    def __init__(self, *args, **kwargs):
        super(PostgresSessionStore, self).__init__(*args, **kwargs)
        #self.dbname = config.get("session_store_dbname", "session_store")
        #self.dbtable = config.get("session_store_dbtable", "odoo_sessions")
        self.dbname = INOUK_SESSION_STORE_DBNAME
        self.dbtable = INOUK_SESSION_STORE_DBTABLE
        self._setup_database(raise_exception=False)

    def _setup_database(self, raise_exception=True):
        _logger.info("Setting up session database '%s'.", self.dbname)
        try:
            with db_connect(self.dbname, allow_uri=True).cursor() as cursor:
                cursor._cnx.autocommit = True
                self._create_table(cursor)
        except:
            self._create_database()
            self._setup_database()

    def _create_database(self):
        _logger.info("Creating sessions database.")
        with db_connect("postgres").cursor() as cursor:
            cursor._cnx.autocommit = True
            cursor.execute(
                f"CREATE DATABASE {self.dbname} ENCODING 'unicode' TEMPLATE 'template0';"
            )

    def _create_table(self, cursor):
        _logger.info("  Checking/creating sessions table in database '%s'.", self.dbname)
        cursor.execute(f"SELECT EXISTS ( SELECT FROM pg_tables WHERE schemaname = 'public' AND tablename  = '{self.dbtable}');")
        _table_exist = cursor.fetchone()[0]
        #print("  table_exist? ", _table_exist)
        if not _table_exist:
            _logger.info("  Session table '%s' does not exists. Trying to create it", self.dbtable)
            try:
                cursor.execute(
                    f"CREATE TABLE IF NOT EXISTS {self.dbtable} ("
                    f"    sid varchar PRIMARY KEY,"
                    f"    db_name VARCHAR,"
                    f"    write_date timestamp without time zone NOT NULL,"
                    f"    payload bytea NOT NULL"
                    f");"
                )
                _logger.info("  Session table '%s' created (%s).", self.dbtable, cursor.statusmessage)
            except:
                _logger.error("  Failed to create missing session table '%s' with error: %s.", self.dbtable, cursor.statusmessage)
                raise

        else:
            _logger.info("  Session table '%s' exists. I will use it.", self.dbtable)

    @contextmanager
    def open_cursor(self):
        connection = db_connect(self.dbname, allow_uri=True)
        cursor = connection.cursor()
        cursor._cnx.autocommit = True
        yield cursor
        cursor.close()

    @retry_database
    def save(self, session):
        with self.open_cursor() as cursor:
            cursor.execute(
                f"INSERT INTO {self.dbtable} (sid, db_name, write_date, payload) "
                f"VALUES (%(sid)s, %(db_name)s, now() at time zone 'UTC', %(payload)s) "
                f"ON CONFLICT (sid) "
                f"DO UPDATE SET payload = %(payload)s, write_date = now() at time zone 'UTC';",
                dict(
                    sid=session.sid,
                    db_name=session.db or None,
                    payload=psycopg2.Binary(
                        pickle.dumps(dict(session), pickle.HIGHEST_PROTOCOL)
                    ),
                ),
            )

    @retry_database
    def delete(self, session):
        with self.open_cursor() as cursor:
            cursor.execute(
                "DELETE FROM {dbtable} WHERE sid=%s;".format(dbtable=self.dbtable),
                [session.sid],
            )

    def rotate(self, session, env, soft=False):
        # Mirrors odoo.http.FilesystemSessionStore.rotate. A *soft* rotation
        # changes only the second half of the sid, keeping the first
        # STORED_SESSION_BYTES (42) chars stable so in-flight requests still
        # carrying the old cookie keep resolving (the old row is retained for
        # SESSION_DELETION_TIMER seconds) and csrf tokens stay valid. A *hard*
        # rotation (login/logout/password change) replaces the whole sid.
        if soft:
            # Concurrent requests may all try to soft-rotate the same session;
            # only the first creates the new sid, the others just follow it.
            static = session.sid[:STORED_SESSION_BYTES]
            recent_session = self.get(session.sid)
            if 'next_sid' in recent_session:
                session.sid = recent_session['next_sid']
                return
            next_sid = static + self.generate_key()[STORED_SESSION_BYTES:]
            session['next_sid'] = next_sid
            session['deletion_time'] = time.time() + SESSION_DELETION_TIMER
            self.save(session)
            # Now switch to the new session; the old row lingers until
            # delete_old_sessions reaps it.
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

    @retry_database
    def get(self, sid):
        if not self.is_valid_key(sid):
            return self.new()
        with self.open_cursor() as cursor:
            cursor.execute(
                """
                SELECT payload, write_date 
                FROM {dbtable} WHERE sid=%s;
            """.format(
                    dbtable=self.dbtable
                ),
                [sid],
            )
            try:
                payload, write_date = cursor.fetchone()
                if write_date.date() != datetime.today().date():
                    cursor.execute(
                        """
                        UPDATE {dbtable} 
                        SET write_date = now() at time zone 'UTC' 
                        WHERE sid=%s;
                    """.format(
                            dbtable=self.dbtable
                        ),
                        [sid],
                    )
                return self.session_class(pickle.loads(payload), sid, False)
            except Exception:
                return self.session_class({}, sid, False)

    @retry_database
    def list(self):
        with self.open_cursor() as cursor:
            cursor.execute("SELECT sid FROM {dbtable};".format(dbtable=self.dbtable))
            return [record[0] for record in cursor.fetchall()]

    @retry_database
    def vacuum(self, max_lifetime=60 * 60 * 24 * 7):
        # Called by Odoo's session GC cron (ir_http._gc_sessions ->
        # session_store.vacuum(max_lifetime=...)). Odoo 18 renamed the old
        # `clean()` entry point to `vacuum()`.
        with self.open_cursor() as cursor:
            cursor.execute(
                f"DELETE FROM {self.dbtable} WHERE now() at time zone 'UTC' - write_date > interval '1 second' * %s;",
                [max_lifetime],
            )

    def clean(self):
        self.vacuum()

    def delete_old_sessions(self, session):
        # Called on every authenticated request via
        # security.check_session() -> session._delete_old_sessions().
        # After a soft rotation the previous session row is kept alive for
        # SESSION_DELETION_TIMER seconds (to serve in-flight requests still
        # carrying the old cookie); once that grace period elapses we reap the
        # whole identifier (old + current rows) and re-save the current one.
        if 'gc_previous_sessions' in session:
            if session['create_time'] + SESSION_DELETION_TIMER < time.time():
                self.delete_from_identifiers([session.sid[:STORED_SESSION_BYTES]])
                del session['gc_previous_sessions']
                self.save(session)

    def generate_key(self, salt=None):
        # Mirrors odoo.http.FilesystemSessionStore.generate_key: an 84-char
        # url-safe base64 key whose first STORED_SESSION_BYTES chars act as a
        # stable identifier across soft rotations.
        key = str(time.time()).encode() + os.urandom(64)
        hash_key = sha512(key).digest()[:-1]  # prevent base64 padding
        return base64.urlsafe_b64encode(hash_key).decode('utf-8')

    def is_valid_key(self, key):
        # Accept both the new 84-char base64 keys and the legacy 40-char sha1
        # hex keys so cookies issued before this upgrade keep working.
        return bool(_base64_urlsafe_re.match(key) or _legacy_sha1_re.match(key))

    @retry_database
    def get_missing_session_identifiers(self, identifiers):
        # Used by res.device(.log) to detect revoked/expired sessions: returns
        # the subset of identifiers (sid[:42] prefixes) that have no session row.
        identifiers = set(identifiers)
        if not identifiers:
            return identifiers
        with self.open_cursor() as cursor:
            cursor.execute(
                f"SELECT DISTINCT left(sid, %s) FROM {self.dbtable} WHERE left(sid, %s) = ANY(%s);",
                [STORED_SESSION_BYTES, STORED_SESSION_BYTES, list(identifiers)],
            )
            present = {record[0] for record in cursor.fetchall()}
        return identifiers - present

    @retry_database
    def delete_from_identifiers(self, identifiers):
        # Delete every session whose sid starts with one of the given 42-char
        # identifiers (used by device revocation and soft-rotation cleanup).
        valid = [i for i in identifiers if _session_identifier_re.match(i)]
        if not valid:
            return
        with self.open_cursor() as cursor:
            cursor.execute(
                f"DELETE FROM {self.dbtable} WHERE left(sid, %s) = ANY(%s);",
                [STORED_SESSION_BYTES, valid],
            )
