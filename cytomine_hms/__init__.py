# -*- coding: utf-8 -*-

# * Copyright (c) 2009-2020. Authors: see NOTICE file.
# *
# * Licensed under the Apache License, Version 2.0 (the "License");
# * you may not use this file except in compliance with the License.
# * You may obtain a copy of the License at
# *
# *      http://www.apache.org/licenses/LICENSE-2.0
# *
# * Unless required by applicable law or agreed to in writing, software
# * distributed under the License is distributed on an "AS IS" BASIS,
# * WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# * See the License for the specific language governing permissions and
# * limitations under the License.

import logging
import time

from colors import colors
from flask import Flask, request, g
from .controller import api


def create_app():
    app = Flask(__name__)
    app.config.from_envvar('CONFIG_FILE')
    app.logger.setLevel(logging.INFO)

    @app.before_request
    def start_timer():
        g.start = time.time()

    @app.after_request
    def log_request(response):
        now = time.time()
        duration = round(now - g.start, 4)
        host = request.host.split(':', 1)[0]
        args = dict(request.args)
        values = dict(request.values)

        log_params = [
            ('method', request.method, 'magenta'),
            ('path', request.path, 'blue'),
            ('status', response.status_code, 'yellow'),
            ('duration', duration, 'green'),
            ('host', host, 'red'),
            ('params', args, 'blue'),
            ('values', values, 'blue')
        ]

        parts = []
        for name, value, color in log_params:
            part = colors.color("{}={}".format(name, value), fg=color)
            parts.append(part)
        line = " ".join(parts)
        app.logger.info(line)

        return response

    app.register_blueprint(api)

    return app
