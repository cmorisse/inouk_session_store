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
    nothing behind, neither a session nor a ``session_id`` cookie.
    """

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
        })
