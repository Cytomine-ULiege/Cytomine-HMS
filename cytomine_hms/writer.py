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

DEBUG = False


def get_image_dimension(image):
    if image.channels > 1:
        return 'channel'
    elif image.depth > 1:
        return 'zStack'
    elif image.duration > 1:
        return 'time'
    else:
        return None


def create_hdf5(
    uploaded_file, image, slices, cf, n_workers=0, tile_size=512,
    n_written_tiles_to_update=50, root=""
):
    image_name = image.originalFilename
    dimension = get_image_dimension(image)
    if not dimension:
        log("{} | ERROR: Cannot make profile for 2D image".format(image_name))
        uploaded_file.status = uploaded_file.ERROR_CONVERSION
        retry_update(uploaded_file)
        return

    path = os.path.join(root, uploaded_file.path)
    dir_path = os.path.dirname(path)
    os.makedirs(dir_path, exist_ok=True)
    hdf5 = h5py.File(path, 'w')

    hdf5.create_dataset("width", data=image.width, shape=())
    hdf5.create_dataset("height", data=image.height, shape=())
    hdf5.create_dataset("nSlices", data=len(slices), shape=())
    bpc = image.bitPerSample if image.bitPerSample else 8
    hdf5.create_dataset("bpc", data=bpc, shape=())

    uploaded_file.status = UploadedFile.CONVERTING
    uploaded_file = retry_update(uploaded_file)
    cf = retry_update(cf)

    dtype = np.uint16 if bpc > 8 else np.uint8
    dataset = hdf5.create_dataset(
        "data", shape=(image.height, image.width, len(slices)), dtype=dtype
    )

    x_tiles = int(np.ceil(image.width / tile_size))
    y_tiles = int(np.ceil(image.height / tile_size))
    n_blocks = x_tiles * y_tiles * len(slices)

    def tile_worker(_in, _out, _error):
        while True:
            if not _out.full():
                item = _in.get()
                if item is None:
                    return
                try:
                    _out.put((item, get_tile(item)))
                    log("{} | Read tile {} {} {}".format(
                        image_name, item['X'], item['Y'], item['slice'].channel
                    ))
                except Exception as e:
                    log(
                        "{} | ERROR tile read: {}".format(image_name, item),
                        force=True
                    )
                    _error.put(e)
                    return
            else:
                if not _error.empty():
                    return
                else:
                    time.sleep(0.5)

    def get_tile(tile_info):
        host = tile_info['slice'].imageServerUrl
        imagepath = tile_info['slice'].path
        url = f"{host}/image/{imagepath}/window.png"
        top_left_x = tile_info['X'] * tile_size
        top_left_y = tile_info['Y'] * tile_size
        parameters = {
            "region": {
                "left": top_left_x,
                "top": top_left_y,
                "width": min(tile_size, image.width - top_left_x),
                "height": min(tile_size, image.height - top_left_y),
            },
            "level": 0,
            "bits": bpc,
            "colorspace": "GRAY",
            "channels": tile_info['slice'].channel,
            "z_slices": tile_info['slice'].zStack,
            "timepoints": tile_info['slice'].time
        }

        response = requests.post(url, json=parameters)
        tile = np.asarray(Image.open(BytesIO(response.content)))
        return tile

    def writer_worker(_out, _error):
        counter = 0
        while True:
            if not _out.empty():
                item = _out.get()
                if item is None:
                    return

                counter = counter + 1
                try:
                    write_tile(*item)

                    if counter % n_written_tiles_to_update == 0 or counter == n_blocks:
                        progress = (counter / n_blocks * 100)
                        cf.progress = int(round(progress))
                        cf.update()
                        log("{} | Write {}% ({}/{})".format(
                            image_name, progress, counter, n_blocks
                        ),)
                except Exception as e:
                    tile_info, _ = item
                    log(
                        "{} | ERROR tile write: {}".format(image_name, tile_info),
                        force=True
                    )
                    _error.put(e)
                    return
            else:
                if not _error.empty():
                    return
                else:
                    time.sleep(0.5)

    def write_tile(tile_info, tile_data):
        height, width = tile_data.shape
        min_row = tile_info['Y'] * tile_size
        max_row = min_row + height
        min_col = tile_info['X'] * tile_size
        max_col = min_col + width
        dataset[min_row:max_row, min_col:max_col, tile_info['slice'].rank] = tile_data

    if n_workers <= 0:
        n_workers = os.cpu_count() - 1

    read_queue = Queue()
    write_queue = Queue(512)
    error_queue = Queue()
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

    read_workers = [
        Thread(target=tile_worker, args=(read_queue, write_queue, error_queue))
        for _ in range(n_workers)
    ]
    for rw in read_workers:
        rw.start()

    time.sleep(0.2)
    write_worker = Thread(target=writer_worker, args=(write_queue, error_queue))
    write_worker.start()

    for rw in read_workers:
        rw.join()

    write_queue.put(None)
    write_worker.join()

    uploaded_file = uploaded_file.fetch()
    cf = cf.fetch()
    if not error_queue.empty():
        uploaded_file.status = uploaded_file.ERROR_CONVERSION
    elif uploaded_file.status == UploadedFile.CONVERTING:
        uploaded_file.status = uploaded_file.CONVERTED

    uploaded_file.size = os.path.getsize(path)
    retry_update(uploaded_file)
    retry_update(cf)

    hdf5.close()


def retry_update(obj, retries=5):
    updated = obj.update()
    while not updated and retries > 0:
        updated = obj.update()
        retries = retries - 1
        time.sleep(1)
    return updated


def log(content, force=False):
    if DEBUG or force:
        print(content)
