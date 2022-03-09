# -*- coding: utf-8 -*-

# * Copyright (c) 2009-2022. Authors: see NOTICE file.
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

import numpy as np
from rasterio.features import geometry_mask
from rasterio.transform import IDENTITY
from shapely.affinity import affine_transform
from shapely.geometry import box, Point, LineString


def change_referential(geometry, height):
    """
    Return the geometry given in cartesian coordinate system to a matrix-like coordinate system.
    :param height: The height of the image having this geometry
    :param geometry: The geometry in cartesian coordinate system
    :return: The geometry in matrix-like coordinate system
    """

    if type(geometry) in [Point, LineString]:
        matrix = [1, 0, 0, -1, 0, height - 1]
    else:
        matrix = [1, 0, 0, -1, 0, height]

    return affine_transform(geometry, matrix)


def prepare_geometry(hdf5, geometry):
    """
    Get a valid geometry in matrix-like coordinate system
    :param hdf5: The HDF5 file the geometry must be valid for
    :param geometry: The geometry in cartesian coordinate system
    :return: A valid geometry in matrix-like coordinate system
    """
    image_width = hdf5['width'][()]
    image_height = hdf5['height'][()]
    image_geometry = box(0, 0, image_width, image_height)
    return change_referential(geometry.intersection(image_geometry), image_height)


def prepare_slices(hdf5, min_slice, max_slice):
    n_slices = hdf5['nSlices'][()]

    if not min_slice or min_slice < 0 or min_slice > n_slices:
        min_slice = 0

    if not max_slice or max_slice < min_slice or max_slice > n_slices:
        max_slice = n_slices

    return min_slice, max_slice


def get_mask(hdf5, geometry):
    image_width = hdf5['width'][()]
    image_height = hdf5['height'][()]
    return geometry_mask([geometry], (image_height, image_width), transform=IDENTITY, invert=True)


def get_bounds(mask):
    i, j = np.nonzero(mask)
    return np.s_[np.min(i):np.max(i)+1, np.min(j):np.max(j)+1]


def extract_profile(hdf5, mask, slices):
    """
    Get profile data as matrix
    :param hdf5: The HD5 file with profile data
    :param mask: The geometry mask
    :param slices: A Python slice of image slices
    :return:
    """
    bounds = get_bounds(mask) + (slice(*slices),)
    return hdf5['data'][bounds]


def get_projection(profile, proj_func, axis=-1):
    return proj_func(profile, axis=axis)


def get_cartesian_indexes(hdf5, mask):
    image_height = hdf5['height'][()]
    y_indexes, x_indexes = mask.nonzero()
    y_indexes = image_height - 1 - y_indexes

    return x_indexes, y_indexes
