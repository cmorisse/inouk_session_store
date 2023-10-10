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

import pickle
import logging
import psycopg2
import functools

from contextlib import closing
from contextlib import contextmanager
from datetime import datetime, date

#from werkzeug.contrib.sessions import SessionStore
from odoo.tools._vendor import sessions

from odoo.sql_db import db_connect
from odoo.tools import config
from odoo.service import security, model as service_model


from ..config import INOUK_SESSION_STORE_DATABASE, INOUK_SESSION_STORE_DBNAME, INOUK_SESSION_STORE_DBTABLE

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
        _logger.info("Setting up session database.")
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
        _logger.info("  Checking/creating sessions table.")
        cursor.execute(f"SELECT EXISTS ( SELECT FROM pg_tables WHERE schemaname = 'public' AND tablename  = '{self.dbtable}');")
        _table_exist = cursor.fetchone()
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
            except:
                _logger.error("  Failed to create missing session table '%s'.", self.dbtable)
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

    def rotate(self, session, env):
        self.delete(session)
        session.sid = self.generate_key()
        if session.uid and env:
            session.session_token = security.compute_session_token(session, env)
        session.should_rotate = False
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
    def clean(self):
        with self.open_cursor() as cursor:
            cursor.execute(
                f"DELETE FROM {self.dbtable} WHERE now() at time zone 'UTC' - write_date > '7 days';"
            )
