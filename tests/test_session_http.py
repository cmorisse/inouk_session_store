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
"""End-to-end HTTP tests for the PostgreSQL session store.

These run a real Odoo server and a real login, so they only mean something when
the postgres backend is actually wired in (``INOUK_SESSION_STORE=postgres``);
otherwise they are skipped to avoid giving false confidence by testing the
stock filesystem store.
"""

import json
from unittest.mock import patch

import odoo.http
from odoo.http import root
from odoo.tests import HttpCase, tagged

from odoo.addons.inouk_session_store.store.postgres import PostgresSessionStore

TEST_LOGIN = "inouk_sstore_test"
TEST_PASSWORD = "inouk_sstore_test"


@tagged("post_install", "-at_install", "inouk_session_store")
class TestSessionHttp(HttpCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.test_user = cls.env["res.users"].create(
            {
                "name": "Inouk SStore Test",
                "login": TEST_LOGIN,
                "password": TEST_PASSWORD,
                "group_ids": [(6, 0, [cls.env.ref("base.group_user").id])],
            }
        )

    def setUp(self):
        super().setUp()
        if not isinstance(root.session_store, PostgresSessionStore):
            self.skipTest(
                "inouk_session_store postgres backend is not active; "
                "set INOUK_SESSION_STORE=postgres to run these tests"
            )

    def _session_info(self):
        """Call a route that requires a valid authenticated session."""
        return self.url_open(
            "/web/session/get_session_info",
            data=json.dumps({"jsonrpc": "2.0", "method": "call", "params": {}}),
            headers={"Content-Type": "application/json"},
        )

    def _sid(self):
        return self.opener.cookies.get("session_id")

    def test_authenticated_request_does_not_crash(self):
        # Regression test for the original failure: Odoo 19 runs
        # security.check_session() -> session._delete_old_sessions() on every
        # authenticated request. The store used to lack delete_old_sessions,
        # raising AttributeError -> "Access Denied".
        self.authenticate(TEST_LOGIN, TEST_PASSWORD)
        resp = self._session_info()
        self.assertEqual(resp.status_code, 200)
        body = resp.json()
        self.assertNotIn("error", body, msg=str(body))
        self.assertEqual(body["result"]["uid"], self.test_user.id)

    def test_session_id_uses_new_key_format(self):
        self.authenticate(TEST_LOGIN, TEST_PASSWORD)
        sid = self._sid()
        self.assertEqual(len(sid), 84)
        self.assertTrue(root.session_store.is_valid_key(sid))

    def test_session_survives_soft_rotation(self):
        self.authenticate(TEST_LOGIN, TEST_PASSWORD)
        old_sid = self._sid()
        # Force the 3h periodic soft rotation to fire on the next request.
        with patch.object(odoo.http, "SESSION_ROTATION_INTERVAL", 0):
            resp = self._session_info()
        self.assertEqual(resp.status_code, 200)
        new_sid = self._sid()
        # rotation happened, but the 42-char identifier prefix is preserved
        self.assertNotEqual(new_sid, old_sid)
        self.assertEqual(new_sid[:42], old_sid[:42])
        # and the user is still authenticated afterwards
        self.assertEqual(
            self._session_info().json()["result"]["uid"], self.test_user.id
        )
