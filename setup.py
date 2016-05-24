from setuptools import setup, find_packages
from setuptools.command.test import test as TestCommand
import sys

try:
    from jupyterpip import cmdclass
except:
    import pip
    import importlib
    pip.main(['install', 'jupyter-pip'])
    cmdclass = importlib.import_module('jupyterpip').cmdclass


class PyTest(TestCommand):
    def finalize_options(self):
        TestCommand.finalize_options(self)
        self.test_args = []
        self.test_suite = True

    def run_tests(self):
        import pytest
        errcode = pytest.main(self.test_args)
        sys.exit(errcode)

INSTALL_REQUIRES = ['astropy>=1.0', 'numpy', 'scipy', 'pillow',
                    'ipython >3.0', 'msumastro>=0.8', 'ccdproc>=0.3',
                    'matplotlib', 'jupyter-pip']


setup(
    name='reducer',
    version='0.2.4',
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
    cmdclass=cmdclass('accordion_replacement'), #{'test': PyTest, ''},
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
