from __future__ import (division, print_function, absolute_import,
                        unicode_literals)

from IPython import version_info


def ipython_version_as_string():
    """
    The IPython version is a tuple (major, minor, patch, vendor). We only
    need major, minor, patch.
    """
    return ''.join([str(s) for s in version_info[0:3]])
