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

import os
from io import BytesIO
from queue import Queue
from threading import Thread

import h5py
import numpy as np
import requests
import time
from PIL import Image
from cytomine.models import UploadedFile

TILE_SIZE = 512


def get_image_dimension(image):
    if image.channels > 1:
        return 'channel'
    elif image.depth > 1:
        return 'zStack'
    elif image.duration > 1:
        return 'time'
    else:
        return None


def create_hdf5(uploaded_file, image, slices , n_workers=0):

    dimension = get_image_dimension(image)
    if not dimension:
        raise ValueError("Cannot make profile for 2D image")

    path = os.path.dirname(uploaded_file.path)
    os.makedirs(path, exist_ok=True)
    hdf5 = h5py.File(uploaded_file.path, 'w')
    image_name = image.originalFilename

    hdf5.create_dataset("width", data=image.width, shape=())
    hdf5.create_dataset("height", data=image.height, shape=())
    hdf5.create_dataset("nSlices", data=len(slices), shape=())
    bpc = image.bitPerSample if image.bitPerSample else 8
    hdf5.create_dataset("bpc", data=bpc, shape=())

    uploaded_file.status = UploadedFile.CONVERTING
    uploaded_file.update()

    dtype = np.uint16 if bpc > 8 else np.uint8
    dataset = hdf5.create_dataset("data", shape=(image.height, image.width, len(slices)), dtype=dtype)

    x_tiles = int(np.ceil(image.width / TILE_SIZE))
    y_tiles = int(np.ceil(image.height / TILE_SIZE))
    n_blocks = x_tiles * y_tiles * len(slices)

    def tile_worker(_in, _out):
        while True:
            if not _out.full():
                item = _in.get()
                if item is None:
                    break
                _out.put((item, get_tile(item)))
            else:
                time.sleep(1)

    def get_tile(tile_info):
        # start = time.time()
        host = tile_info['slice'].imageServerUrl
        parameters = {
            "fif": tile_info['slice'].path,
            "mimeType": tile_info['slice'].mime,
            "topLeftX": tile_info['X'] * TILE_SIZE,
            "topLeftY": image.height - (tile_info['Y'] * TILE_SIZE),
            "width": TILE_SIZE,
            "height": TILE_SIZE,
            "imageWidth": image.width,
            "imageHeight": image.height,
            "bits": bpc,
        }
        url = "{}/slice/crop.png".format(host)
        response = requests.get(url, parameters)
        # print(response.url)
        tile = np.asarray(Image.open(BytesIO(response.content)))
        # end = time.time()
        # print(end - start)
        return tile

    def writer_worker(_out):
        counter = 0
        while True:
            item = _out.get()
            if item is None:
                return

            counter = counter + 1
            write_tile(*item)

            if counter % 30 == 0 or counter == n_blocks:
                print("{} - Write {}% ({}/{})".format(image_name, (counter/n_blocks*100), counter, n_blocks))

    def write_tile(tile_info, tile_data):
        height, width = tile_data.shape
        min_row = tile_info['Y'] * TILE_SIZE
        max_row = min_row + height
        min_col = tile_info['X'] * TILE_SIZE
        max_col = min_col + width
        # print("Write {}:{} {}:{} {}".format(min_row, max_row, min_col, max_col, tile_info['slice'].rank))
        dataset[min_row:max_row, min_col:max_col, tile_info['slice'].rank] = tile_data

    if n_workers <= 0:
        n_workers = os.cpu_count() - 1

    read_queue = Queue()
    write_queue = Queue()
    for _slice in slices:
        for x in range(x_tiles):
            for y in range(y_tiles):
                read_queue.put({
                    "X": x,
                    "Y": y,
                    "tileIndex": x + (y * x_tiles),
                    "slice": _slice
                })

    for _ in range(n_workers):
        read_queue.put(None)

    read_workers = [Thread(target=tile_worker, args=(read_queue, write_queue)) for _ in range(n_workers)]
    for rw in read_workers:
        rw.start()

    write_worker = Thread(target=writer_worker, args=(write_queue,))
    write_worker.start()

    for rw in read_workers:
        rw.join()

    write_queue.put(None)
    write_worker.join()

    if uploaded_file.status == UploadedFile.CONVERTING:
        uploaded_file.status = uploaded_file.CONVERTED
        uploaded_file.size = os.path.getsize(uploaded_file.path)
        uploaded_file.update()

    hdf5.close()
