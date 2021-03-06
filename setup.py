from setuptools import find_packages, setup

setup(
    name='cytomine_hms',
    version='1.1.0',
    packages=find_packages(),
    include_package_data=True,
    zip_safe=False,
    install_requires=[
        'flask',
        'requests',
        'rasterio',
        'h5py',
        'shapely',
        'numpy',
        'pillow',
        'cytomine-python-client',
        'ansicolors'
    ],
)