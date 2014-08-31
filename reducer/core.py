from __future__ import (division, print_function, absolute_import,
                        unicode_literals)

import os
import shutil

from .notebook_dir import get_notebook_path

__all__ = ['main']


def main():
    notebook_template = get_notebook_path()
    working_dir = os.getcwd()
    dest_name = 'reduction.ipynb'
    dest_path = os.path.join(working_dir, dest_name)
    if os.path.exists(dest_path):
        raise RuntimeError("Notebook named {} already exists; "
                           "remove before running reducer.".format(dest_name))
    shutil.copy(notebook_template, dest_path)


if __name__ == '__main__':
    main()
