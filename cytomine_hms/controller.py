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
from io import BytesIO
from threading import Thread

import h5py
import numpy as np
from PIL import Image
from cytomine import Cytomine
from cytomine.models import UploadedFile, AbstractImage, AbstractSliceCollection
from shapely import wkt
from shapely.geometry import Point

from .writer import create_hdf5
from .reader import prepare_geometry, prepare_slices, get_mask, extract_profile, get_cartesian_indexes, \
    get_projection, get_bounds
from .utils import NumpyEncoder, CompanionFile
from flask import abort, request, send_file, g, Blueprint, current_app

api = Blueprint('api', __name__)


def get_core_connection():
    if 'cytomine' not in g:
        g.cytomine = Cytomine.connect(
            current_app.config['CYTOMINE_HOST'],
            current_app.config['CYTOMINE_PUBLIC_KEY'],
            current_app.config['CYTOMINE_PRIVATE_KEY']
        )
    return g.cytomine


@api.route('/')
def hello_world():
    return 'Hello World!'


@api.route('/hdf5.json', methods=['GET', 'POST'])
def make_hdf5():
    uploaded_file_id = _get_parameter()('uploadedFile')
    image_id = _get_parameter()('image')
    companion_file_id = _get_parameter()('companionFile')

    get_core_connection()
    uploaded_file = UploadedFile().fetch(uploaded_file_id)
    image = AbstractImage().fetch(image_id)
    slices = AbstractSliceCollection().fetch_with_filter("abstractimage", image.id)
    cf = CompanionFile().fetch(companion_file_id)

    n_workers = current_app.config['N_TILE_READER_WORKERS']
    tile_size = current_app.config['TILE_SIZE']
    n_written_tiles_to_update = current_app.config['N_WRITTEN_TILES_TO_UPDATE_PROGRESS']
    thread = Thread(target=create_hdf5, args=(uploaded_file, image, slices, cf, n_workers, tile_size,
                                              n_written_tiles_to_update))
    thread.daemon = True
    thread.start()

    return {'started': True}


@api.route('/profile.json', methods=['GET', 'POST'])
def get_profile():
    path = _get_parameter()('fif', type=str)
    geometry = wkt.loads(_get_parameter()('location', type=str))
    if path is None or geometry is None:
        abort(400)

    min_slice = _get_parameter()('minSlice', None, type=int)
    max_slice = _get_parameter()('maxSlice', None, type=int)

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

    if type(geometry) == Point and len(response) == 1:
        response = response[0]

    return json.dumps(response, cls=NumpyEncoder, check_circular=False)


@api.route('/profile/projections.json', methods=['GET', 'POST'])
def get_profile_stats():
    path = _get_parameter()('fif', type=str)
    geometry = wkt.loads(_get_parameter()('location', type=str))
    if path is None or geometry is None:
        abort(400)

    min_slice = _get_parameter()('minSlice', None, type=int)
    max_slice = _get_parameter()('maxSlice', None, type=int)

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


@api.route('/profile/min-projection.<format>', methods=['GET', 'POST'])
def get_profile_min_projection(format):
    return _get_profile_image_projection(np.min, format)


@api.route('/profile/max-projection.<format>', methods=['GET', 'POST'])
def get_profile_max_projection(format):
    return _get_profile_image_projection(np.max, format)


@api.route('/profile/average-projection.<format>', methods=['GET', 'POST'])
def get_profile_average_projection(format):
    return _get_profile_image_projection(np.mean, format)


def _get_profile_image_projection(proj_func, format):
    path = _get_parameter()('fif', type=str)
    geometry = wkt.loads(_get_parameter()('location', type=str))
    if path is None or geometry is None:
        abort(400)

    min_slice = _get_parameter()('minSlice', None, type=int)
    max_slice = _get_parameter()('maxSlice', None, type=int)

    hdf5 = h5py.File(path, 'r')
    geometry = prepare_geometry(hdf5, geometry)
    slices = prepare_slices(hdf5, min_slice, max_slice)

    mask = get_mask(hdf5, geometry)
    profile = extract_profile(hdf5, mask, slices)

    projection = get_projection(profile, proj_func).astype(profile.dtype)
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


def _get_parameter():
    if request.method == 'POST':
        return request.values.get
    else:
        return request.args.get
