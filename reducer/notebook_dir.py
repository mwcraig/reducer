from __future__ import (division, print_function, absolute_import,
                        unicode_literals)

import os
import tarfile
import tempfile

from reducer import NOTEBOOK_TEMPLATE_NAME


def get_notebook_path():
    """
    Return the absolute path to the template ipython notebook.

    Returns
    -------
    str
        Name of path
    """
    notebook_name = NOTEBOOK_TEMPLATE_NAME
    this_dir = os.path.dirname(os.path.abspath(__file__))
    notebook_path = os.path.join(this_dir, notebook_name)
    return notebook_path


def get_data_path():
    """
    Return the absolute path to the folder containing package data.

    Returns
    -------
    str
        Name of path
    """
    compressed_base_name = 'mini_versions'
    this_dir = os.path.dirname(os.path.abspath(__file__))
    compressed_data_dir = os.path.join(this_dir, 'data')
    compressed_data = tarfile.open(os.path.join(compressed_data_dir,
                                                compressed_base_name + '.tbz2'))
    temp_dir = tempfile.mkdtemp()
    compressed_data.extractall(temp_dir)
    data_dir = os.path.join(temp_dir, compressed_base_name)
    return data_dir
