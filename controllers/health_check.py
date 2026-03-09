# -*- coding: utf-8 -*-
import json
import logging

from odoo import http
from odoo.http import request

_logger = logging.getLogger(__name__)

try:  # v16
    from odoo.addons.web.controllers.session import Session
except: # before v16
    from odoo.addons.web.controllers.main import Session



class InoukHealthCheck(Session):
    @http.route('/inouk_health_check', type='http', auth="none")
    def inouk_health_check(self):
        request.env.cr.execute("SELECT pg_is_in_recovery();")
        _r = request.env.cr.dictfetchall()
        if _r:
            cluster_is_standby = _r[0].get('pg_is_in_recovery')
            _response_dict = {
                "replication_status":  "cluster_is_standby" if cluster_is_standby else "cluster_is_primary"
            }
        else:
            _response_dict = _r
        return json.dumps(_response_dict)
