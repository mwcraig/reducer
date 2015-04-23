from setuptools import setup, find_packages
from setuptools.command.test import test as TestCommand
import sys


class PyTest(TestCommand):
    def finalize_options(self):
        TestCommand.finalize_options(self)
        self.test_args = []
        self.test_suite = True

    def run_tests(self):
        import pytest
        errcode = pytest.main(self.test_args)
        sys.exit(errcode)

ADD_THESE_BACK_TO_INSTALL_EVENTUALLY = ['photutils']

INSTALL_REQUIRES = ['astropy>=1.0', 'numpy', 'scipy', 'pillow',
                    'ipython >2.0, < 3', 'msumastro>=0.8', 'ccdproc>=0.3']


setup(
    name='reducer',
    version='0.1.dev9',
    description='Process FITS files',
    url='http://github.com/mwcraig/reducer',
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
    cmdclass={'test': PyTest},
    entry_points={
        'console_scripts': [
            ('reducer = '
             'reducer:main')
        ]
    },
    classifiers=['Development Status :: 4 - Beta',
                 'License :: OSI Approved :: BSD License',
                 'Programming Language :: Python :: 2.7',
                 'Programming Language :: Python :: 2 :: Only',
                 'Programming Language :: Python :: 3',
                 'Intended Audience :: Science/Research',
                 'Topic :: Scientific/Engineering :: Astronomy'],
    )
