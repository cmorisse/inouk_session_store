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

from odoo import http
from odoo.http import request


class InoukHealthCheck(http.Controller):
    """Report whether the PostgreSQL this server writes to is a primary or a standby.

    Muppy polls this endpoint on every App Server of an HA pack: ``cluster_is_standby``
    is the healthy answer on the standby, and no answer at all is what the supervision
    reads as broken. The addon is server-wide, so the route is served on every database.
    The route is session-less by contract (``save_session=False``): a probe leaves
    nothing behind, neither a session nor a ``session_id`` cookie. Alongside the
    replication status the answer carries ``versions``, a list the installed modules fill
    in themselves -- see ``_health_check_versions``.
    """

    def _health_check_versions(self):
        """Components that want to publish their version append an entry here.

        The base answer is an empty list: this addon publishes nothing about itself. An
        interested module inherits this controller and extends the list -- Odoo composes
        every subclass of a controller into one class, so several modules can contribute
        without knowing each other:

            class MyHealthCheck(InoukHealthCheck):
                def _health_check_versions(self):
                    versions = super()._health_check_versions()
                    versions.append({'name': 'my_app', 'version': my_version()})
                    return versions

        Each entry is a dict with at least ``name`` and ``version``, so a contributor can
        add a field later without breaking a reader. The route is ``auth='none'``: publish
        only what may be public.
        """
        return []

    @http.route('/inouk_health_check', type='http', auth='none', methods=['GET'],
                csrf=False, save_session=False, readonly=False)
    def inouk_health_check(self):
        # readonly=False on purpose: the question is about the node THIS server writes to.
        # With db_replica_host set, the default (readonly=True for auth='none') would run
        # the SELECT on the replica and a healthy primary would report itself as standby.
        request.env.cr.execute("SELECT pg_is_in_recovery()")
        [(in_recovery,)] = request.env.cr.fetchall()
        return request.make_json_response({
            'replication_status': 'cluster_is_standby' if in_recovery else 'cluster_is_primary',
            'versions': self._health_check_versions(),
        })
