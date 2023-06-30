# -*- coding: utf-8 -*-
# Part of Odoo. See LICENSE file for full copyright and licensing details.

import babel.messages.pofile
import base64
import copy
import datetime
import functools
import glob
import hashlib
import io
import itertools
import jinja2
import json
import logging
import operator
import os
import re
import sys
import tempfile
import time

import werkzeug
import werkzeug.exceptions
import werkzeug.utils
import werkzeug.wrappers
import werkzeug.wsgi
from collections import OrderedDict, defaultdict, Counter
from werkzeug.urls import url_decode, iri_to_uri
from lxml import etree
import unicodedata


import odoo
import odoo.modules.registry
from odoo.api import call_kw, Environment
from odoo.modules import get_module_path, get_resource_path
from odoo.tools import image_process, topological_sort, html_escape, pycompat, ustr, apply_inheritance_specs, lazy_property, float_repr
from odoo.tools.mimetypes import guess_mimetype
from odoo.tools.translate import _
from odoo.tools.misc import str2bool, xlsxwriter, file_open
from odoo.tools.safe_eval import safe_eval
from odoo import http, tools
from odoo.http import content_disposition, dispatch_rpc, request, serialize_exception as _serialize_exception, Response
from odoo.exceptions import AccessError, UserError, AccessDenied
from odoo.models import check_method_name
from odoo.service import db, security

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
