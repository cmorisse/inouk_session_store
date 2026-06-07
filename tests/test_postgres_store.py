###################################################################################
#
#    Copyright (c) 2021 Cyril MORISSE (@cmorisse)
#
#    This file is part of Inouk Session Store
#    (see https://gitub.com/cmorisse/inouk_session_store).
#
#    Released under LGPL-3 (see the LICENSE shipped with this addon).
#
###################################################################################
"""Unit tests for the PostgreSQL session store.

These exercise the store in isolation, against the *test* database but using a
dedicated table, so the live ``inouk_odoo_sessions`` table is never touched.
The store writes with autocommit (outside Odoo's transaction), hence the table
is truncated before each test and dropped in ``tearDownClass`` rather than
relying on transaction rollback.
"""

import time

from odoo.http import Session, STORED_SESSION_BYTES, SESSION_DELETION_TIMER
from odoo.tools._vendor import sessions
from odoo.tests import TransactionCase, tagged

from odoo.addons.inouk_session_store.store.postgres import PostgresSessionStore

TEST_TABLE = "inouk_session_store_unittest"


@tagged("post_install", "-at_install", "inouk_session_store")
class TestPostgresSessionStore(TransactionCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        # Build a store bound to the test DB with a dedicated table. We bypass
        # __init__ (which would run _setup_database against the *configured*
        # table) and wire the attributes by hand.
        store = PostgresSessionStore.__new__(PostgresSessionStore)
        sessions.SessionStore.__init__(store, session_class=Session)
        store.dbname = cls.env.cr.dbname
        store.dbtable = TEST_TABLE
        with store.open_cursor() as cr:
            cr.execute("DROP TABLE IF EXISTS %s;" % TEST_TABLE)
            store._create_table(cr)
        cls.store = store

    @classmethod
    def tearDownClass(cls):
        with cls.store.open_cursor() as cr:
            cr.execute("DROP TABLE IF EXISTS %s;" % TEST_TABLE)
        super().tearDownClass()

    def setUp(self):
        super().setUp()
        # Isolate each test: the store commits outside our transaction.
        with self.store.open_cursor() as cr:
            cr.execute("TRUNCATE TABLE %s;" % TEST_TABLE)

    def _new_session(self, **values):
        s = self.store.new()
        s["uid"] = False  # keeps rotate() out of the session-token branch
        s["create_time"] = time.time()
        s.update(values)
        return s

    # -- key generation / validation --------------------------------------

    def test_generate_key_is_84_char_base64(self):
        key = self.store.generate_key()
        self.assertEqual(len(key), 84)
        self.assertTrue(self.store.is_valid_key(key))

    def test_is_valid_key_accepts_legacy_sha1(self):
        # 40-char hex sids issued before this upgrade must keep working.
        self.assertTrue(self.store.is_valid_key("a" * 40))
        self.assertFalse(self.store.is_valid_key("not-a-valid-key"))

    # -- save / get roundtrip ---------------------------------------------

    def test_save_get_roundtrip(self):
        s = self._new_session(hello="world")
        self.store.save(s)
        self.assertEqual(self.store.get(s.sid).get("hello"), "world")

    def test_get_unknown_sid_returns_empty_session(self):
        self.assertEqual(dict(self.store.get(self.store.generate_key())), {})

    # -- hard rotation ----------------------------------------------------

    def test_hard_rotation_replaces_whole_sid(self):
        s = self._new_session(hello="world")
        self.store.save(s)
        old_sid = s.sid
        self.store.rotate(s, None, soft=False)
        self.assertNotEqual(s.sid, old_sid)
        self.assertEqual(len(s.sid), 84)
        # old row gone, payload migrated to the new sid
        self.assertIsNone(self.store.get(old_sid).get("hello"))
        self.assertEqual(self.store.get(s.sid).get("hello"), "world")

    # -- soft rotation ----------------------------------------------------

    def test_soft_rotation_keeps_identifier_and_old_row(self):
        s = self._new_session(hello="world")
        self.store.save(s)
        old_sid = s.sid
        self.store.rotate(s, None, soft=True)
        new_sid = s.sid
        # the 42-char identifier prefix is preserved -> csrf tokens survive
        self.assertEqual(
            new_sid[:STORED_SESSION_BYTES], old_sid[:STORED_SESSION_BYTES]
        )
        self.assertNotEqual(new_sid, old_sid)
        # both rows are live during the grace window -> in-flight requests
        # still carrying the old cookie keep resolving
        self.assertEqual(self.store.get(old_sid).get("hello"), "world")
        self.assertEqual(self.store.get(new_sid).get("hello"), "world")
        self.assertIn("gc_previous_sessions", s)

    def test_concurrent_soft_rotation_follows_existing_next_sid(self):
        # A second request still holding the old sid must adopt the new sid
        # created by the first rotation instead of diverging.
        s = self._new_session(hello="world")
        self.store.save(s)
        old_sid = s.sid
        self.store.rotate(s, None, soft=True)
        produced = s.sid
        other = self.store.get(old_sid)  # concurrent handle on the old sid
        self.store.rotate(other, None, soft=True)
        self.assertEqual(other.sid, produced)

    # -- delete_old_sessions (per-request GC hook) ------------------------

    def test_delete_old_sessions_keeps_old_within_grace_window(self):
        s = self._new_session(hello="world")
        self.store.save(s)
        old_sid = s.sid
        self.store.rotate(s, None, soft=True)  # create_time reset to now
        self.store.delete_old_sessions(s)
        self.assertEqual(self.store.get(old_sid).get("hello"), "world")

    def test_delete_old_sessions_reaps_old_after_grace_window(self):
        s = self._new_session(hello="world")
        self.store.save(s)
        old_sid = s.sid
        self.store.rotate(s, None, soft=True)
        new_sid = s.sid
        # pretend the grace window has elapsed
        s["create_time"] = time.time() - (SESSION_DELETION_TIMER + 10)
        self.store.save(s)
        self.store.delete_old_sessions(s)
        self.assertIsNone(self.store.get(old_sid).get("hello"))
        self.assertEqual(self.store.get(new_sid).get("hello"), "world")
        self.assertNotIn("gc_previous_sessions", s)

    def test_delete_old_sessions_noop_without_flag(self):
        s = self._new_session(hello="world")
        self.store.save(s)
        # no gc_previous_sessions -> nothing happens, session preserved
        self.store.delete_old_sessions(s)
        self.assertEqual(self.store.get(s.sid).get("hello"), "world")

    # -- identifier helpers (res.device revocation) -----------------------

    def test_get_missing_session_identifiers(self):
        s = self._new_session()
        self.store.save(s)
        ident = s.sid[:STORED_SESSION_BYTES]
        absent = "z" * STORED_SESSION_BYTES
        missing = self.store.get_missing_session_identifiers([ident, absent])
        self.assertNotIn(ident, missing)
        self.assertIn(absent, missing)

    def test_get_missing_session_identifiers_empty_input(self):
        self.assertEqual(self.store.get_missing_session_identifiers([]), set())

    def test_delete_from_identifiers_revokes_session(self):
        s = self._new_session()
        self.store.save(s)
        self.store.delete_from_identifiers([s.sid[:STORED_SESSION_BYTES]])
        self.assertNotIn(s.sid, self.store.list())

    def test_delete_from_identifiers_ignores_malformed(self):
        # malformed / legacy identifiers are skipped, never raise
        s = self._new_session()
        self.store.save(s)
        self.store.delete_from_identifiers(["too-short"])
        self.assertIn(s.sid, self.store.list())

    # -- vacuum / clean (cron GC) -----------------------------------------

    def test_vacuum_respects_max_lifetime(self):
        s = self._new_session()
        self.store.save(s)
        self.store.vacuum(max_lifetime=3600)  # session is fresh -> kept
        self.assertIn(s.sid, self.store.list())
        self.store.vacuum(max_lifetime=0)  # everything older than "now" -> gone
        self.assertNotIn(s.sid, self.store.list())

    def test_clean_is_vacuum_alias(self):
        s = self._new_session()
        self.store.save(s)
        self.store.clean()  # default 7-day lifetime -> recent session kept
        self.assertIn(s.sid, self.store.list())
