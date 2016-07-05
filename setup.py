from setuptools import setup, find_packages
from setuptools.command.test import test as TestCommand
import sys

import versioneer

class PyTest(TestCommand):
    def finalize_options(self):
        TestCommand.finalize_options(self)
        self.test_args = []
        self.test_suite = True

    def run_tests(self):
        import pytest
        errcode = pytest.main(self.test_args)
        sys.exit(errcode)

INSTALL_REQUIRES = [
    'astropy>=1.0',  # For several things...
    'numpy',
    'scipy',
    'scikit-image',
    'ipywidgets >=4.0.1,<5',  # This will pull in jupyter, etc.
    'msumastro>=0.9',  # For TableTree
    'ccdproc>=1',  # For reduction tasks
    'matplotlib',  # Image display
    'dask'  # Required by scikit-image
]


setup(
    name='reducer',
    version=versioneer.get_version(),
    description='Process FITS files',
    url='http://reducer.readthedocs.org',
    long_description=(open('README.rst').read()),
    license='BSD 3-clause',
    author='Matt Craig',
    author_email='mcraig@mnstate.edu',
    packages=find_packages(exclude=['tests*']),
    include_package_data=True,
    install_requires=INSTALL_REQUIRES,
    extras_require={
        'docs': ['numpydoc', 'sphinx-argparse', 'sphinx_rtd_theme'],
    },
    tests_require=['pytest>1.4'] + INSTALL_REQUIRES,
    cmdclass=versioneer.get_cmdclass(),
    # cmdclass=cmdclass('accordion_replacement'),  #{'test': PyTest, ''},
    entry_points={
        'console_scripts': [
            ('reducer = '
             'reducer:main')
        ]
    },
    classifiers=['Development Status :: 4 - Beta',
                 'License :: OSI Approved :: BSD License',
                 'Programming Language :: Python :: 2.7',
                 'Programming Language :: Python :: 3',
                 'Intended Audience :: Science/Research',
                 'Topic :: Scientific/Engineering :: Astronomy'],
)
