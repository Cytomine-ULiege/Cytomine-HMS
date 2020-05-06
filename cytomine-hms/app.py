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

import json
import logging
import time
from io import BytesIO
from threading import Thread

import h5py
import numpy as np
from PIL import Image
from colors import colors
from cytomine import Cytomine
from cytomine.models import UploadedFile, AbstractImage, AbstractSliceCollection
from shapely import wkt
from shapely.geometry import Point

from .writer import create_hdf5
from .reader import prepare_geometry, prepare_slices, get_mask, extract_profile, get_cartesian_indexes, \
    get_projection, get_bounds
from .utils import NumpyEncoder
from flask import Flask, abort, request, send_file, g

app = Flask(__name__)
app.config.from_object('cytomine-hms.config.Config')
app.logger.setLevel(logging.INFO)


@app.route('/')
def hello_world():
    return 'Hello World!'


@app.route('/profile.json', methods=['POST'])
def make_hdf5():
    uploaded_file_id = request.form['uploadedFile']
    image_id = request.form['image']
    companion_file_id = request.form['companionFile']

    Cytomine.connect(app.config['CYTOMINE_HOST'], app.config['CYTOMINE_PUBLIC_KEY'], app.config['CYTOMINE_PRIVATE_KEY'])
    uploaded_file = UploadedFile().fetch(uploaded_file_id)
    image = AbstractImage().fetch(image_id)
    slices = AbstractSliceCollection().fetch_with_filter("abstractimage", image.id)

    n_workers = 4  # TODO
    thread = Thread(target=create_hdf5, args=(uploaded_file, image, slices, n_workers))
    thread.daemon = True
    thread.start()

    return {'started': True}


@app.route('/profile.json', methods=['GET'])
def get_profile():
    path = request.args.get('path')
    geometry = wkt.loads(request.args.get('geometry'))
    if path is None or geometry is None:
        abort(400)

    min_slice = request.args.get('minSlice', None, type=int)
    max_slice = request.args.get('maxSlice', None, type=int)

    hdf5 = h5py.File(path, 'r')
    geometry = prepare_geometry(hdf5, geometry)
    slices = prepare_slices(hdf5, min_slice, max_slice)

    mask = get_mask(hdf5, geometry)
    profile = extract_profile(hdf5, mask, slices)
    profile_mask = mask[get_bounds(mask)]
    profile = profile[profile_mask.nonzero()]

    X, Y = get_cartesian_indexes(hdf5, mask)
    response = []
    for x, y, data in zip(X, Y, profile):
        response.append({
            "point": [x, y],
            "profile": data
        })

    return json.dumps(response, cls=NumpyEncoder, check_circular=False)


@app.route('/profile/stats.json')
def get_profile_stats():
    path = request.args.get('path')
    geometry = wkt.loads(request.args.get('geometry'))
    if path is None or geometry is None:
        abort(400)

    min_slice = request.args.get('minSlice', None, type=int)
    max_slice = request.args.get('maxSlice', None, type=int)

    hdf5 = h5py.File(path, 'r')
    geometry = prepare_geometry(hdf5, geometry)
    slices = prepare_slices(hdf5, min_slice, max_slice)

    mask = get_mask(hdf5, geometry)
    profile = extract_profile(hdf5, mask, slices)
    profile_mask = mask[get_bounds(mask)]
    profile = profile[profile_mask.nonzero()]

    minimums = get_projection(profile, np.min)
    maximums = get_projection(profile, np.max)
    averages = get_projection(profile, np.mean)

    X, Y = get_cartesian_indexes(hdf5, mask)
    response = []
    for x, y, mini, maxi, avg in zip(X, Y, minimums, maximums, averages):
        response.append({
            "point": [x, y],
            "min": mini,
            "max": maxi,
            "average": avg
        })

    return json.dumps(response, cls=NumpyEncoder, check_circular=False)


@app.route('/profile/min-projection.<format>')
def get_profile_min_projection(format):
    return _get_profile_image_projection(np.min, format)


@app.route('/profile/max-projection.<format>')
def get_profile_max_projection(format):
    return _get_profile_image_projection(np.max, format)


@app.route('/profile/average-projection.<format>')
def get_profile_average_projection(format):
    return _get_profile_image_projection(np.mean, format)


def _get_profile_image_projection(proj_func, format):
    path = request.args.get('path')
    geometry = wkt.loads(request.args.get('geometry'))
    if path is None or geometry is None:
        abort(400)

    min_slice = request.args.get('minSlice', None, type=int)
    max_slice = request.args.get('maxSlice', None, type=int)

    hdf5 = h5py.File(path, 'r')
    geometry = prepare_geometry(hdf5, geometry)
    slices = prepare_slices(hdf5, min_slice, max_slice)

    mask = get_mask(hdf5, geometry)
    profile = extract_profile(hdf5, mask, slices)

    projection = get_projection(profile, proj_func)
    masked_projection = projection * mask[get_bounds(mask)]

    bpc = hdf5['bpc'][()]
    if bpc > 8 or format not in ['jpg', 'png']:
        format = 'png'

    img = Image.fromarray(masked_projection)
    img_io = BytesIO()
    img.save(img_io, format)
    img_io.seek(0)
    mime_type = "image/jpeg" if format == "jpg" else "image/png"
    return send_file(img_io, mimetype=mime_type)


@app.before_request
def start_timer():
    g.start = time.time()


@app.after_request
def log_request(response):
    now = time.time()
    duration = round(now - g.start, 4)
    host = request.host.split(':', 1)[0]
    args = dict(request.args)

    log_params = [
        ('method', request.method, 'magenta'),
        ('path', request.path, 'blue'),
        ('status', response.status_code, 'yellow'),
        ('duration', duration, 'green'),
        ('host', host, 'red'),
        ('params', args, 'blue')
    ]

    parts = []
    for name, value, color in log_params:
        part = colors.color("{}={}".format(name, value), fg=color)
        parts.append(part)
    line = " ".join(parts)
    app.logger.info(line)

    return response


if __name__ == '__main__':
    app.run()

