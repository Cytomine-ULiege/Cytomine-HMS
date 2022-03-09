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
import json

from cytomine.models import Model


class NumpyEncoder(json.JSONEncoder):
    """ Special json encoder for numpy types """

    def default(self, obj):
        if isinstance(obj, (np.int_, np.intc, np.intp, np.int8,
                            np.int16, np.int32, np.int64, np.uint8,
                            np.uint16, np.uint32, np.uint64)):
            return int(obj)
        elif isinstance(obj, (np.float_, np.float16, np.float32,
                              np.float64)):
            return float(obj)
        elif isinstance(obj, (np.ndarray,)):
            return obj.tolist()
        return json.JSONEncoder.default(self, obj)


class CompanionFile(Model):
    def __init__(
        self, uploaded_file_id=None, image_id=None, original_filename=None,
        filename=None, type=None, progress=None, **attributes
    ):
        super(CompanionFile, self).__init__()
        self.uploadedFile = uploaded_file_id
        self.image = image_id
        self.originalFilename = original_filename
        self.filename = filename
        self.type = type
        self.progress = progress
        self.populate(attributes)


def convert_axis(axes):
    if axes is not None and axes.lower() in ['xy', 'x,y']:
        return 0

    return 1
