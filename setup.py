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

from setuptools import find_packages, setup

# Package meta-data.
NAME = 'cytomine_hms'
VERSION = '1.2.0'
REQUIRES_PYTHON = '>=3.8.0'

# What packages are required for this module to be executed?
REQUIRED = [
    'flask>=2.0.3',
    'requests>=2.27.1',
    'ansicolors>=1.1.8',

    'h5py>=3.6.0',
    'numpy>=1.20.1',
    'Pillow>=8.0.0',

    'Shapely>=1.8.0',
    'rasterio>=1.2.1',

    # Must be at end to work with dependency links
    'cytomine-python-client>=2.8.3',
]

DEPENDENCY_LINKS = [
    'https://packagecloud.io/cytomine-uliege/Cytomine-python-client/pypi/simple/cytomine-python-client/'
]

setup(
    name=NAME,
    version=VERSION,
    packages=find_packages(),
    python_requires=REQUIRES_PYTHON,
    install_requires=REQUIRED,
    dependency_links=DEPENDENCY_LINKS,
    include_package_data=True,
    classifiers=[
        # Trove classifiers
        # Full list: https://pypi.python.org/pypi?%3Aaction=list_classifiers
        'License :: OSI Approved :: Apache Software License',
        'Programming Language :: Python',
        'Programming Language :: Python :: 3',
        'Programming Language :: Python :: 3.8',
        'Programming Language :: Python :: 3.9',
        'Programming Language :: Python :: Implementation :: CPython',
    ],
)
