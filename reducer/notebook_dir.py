from __future__ import (division, print_function, absolute_import,
                        unicode_literals)

import os

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
