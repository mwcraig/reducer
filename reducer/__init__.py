# keep this at the top -- name is needed for imports to succeed
NOTEBOOK_TEMPLATE_NAME = 'reducer-template.ipynb'

from .core import *

from ._version import get_versions
__version__ = get_versions()['version']
del get_versions
