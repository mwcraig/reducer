This package provides a Jupyter notebook for reducing CCD data.

Documentation is at: https://reducer.readthedocs.org

.. image:: http://img.shields.io/badge/powered%20by-AstroPy-orange.svg?style=flat :target:http://astropy.org

Please provide feedback
=======================

Comments are very, very much welcome. Please comment by `making a new
issue on Github <https://github.com/mwcraig/reducer/issues>`__ (if, by
chance, a reasonably senior academic is using this, you can send
feedback by email; anyone else should *really* create a github account
so you can make an issue :)).

Installation
============


**Note about IPython/Jupyter version support:** Version 0.3 and higher of
reducer works with IPython 4/Jupyter. Version 0.1 works with IPython 2, and
Version 0.2.x work with IPython 3 or IPython 4/Jupyter. No improvements to
``reducer`` will be backported to version 0.1.x/IPython 2 or to 0.2.x/IPYthon
3. Feel free to fork if you need that!

You need python (2.7, or 3.4 or higher) and the `SciPy
stack <http://scipy.org>`__. The easiest way to the get the full stack
is from a distribution like `anaconda <http://continuum.io>`__.

On Windows it will be easiest to install using the Anaconda Python
distribution and ``conda`` (because everything has been compiled for you).

To install using ``conda``:

::

    conda install -c conda-forge -c astropy reducer


If you prefer, you can install with pip in any python distribution (but may
end up compiling some of the dependencies):

::

    pip install reducer


You can, if you want, grab the source on github (there is a "Download as
ZIP" link on the right you can use if you don't want to mess git),
change into the source directory, and run ``python setup.py install``.

.. note::

    `reducer` comes with a small set of images; the download size is roughly
    13MB. It is provided so you can try the notebook without needing your own
    data. If you run the notebook as-is then the sample images will get
    expanded to 300MB in a temporary directory.


Usage
=====

This package doesn't magically do your reduction for you. Instead, it
creates a template `jupyter notebook <http://jupyter.org>`_ that leads
you through data reduction. When you are done
you have reduced your data and *you have a notebook that allows you or
someone else to reproduce your work*.

In a terminal, navigate to the directory where you want to keep the
notebook for doing your reduction (which does not have to be the same
directory where the data is, though it can be), then type::

    reducer

This will create a new template notebook. To open the notebook, type
in a terminal::

    jupyter notebook

A browser window will open; the notebook you want is named "reduction.ipynb".
Click on it, then just do what it says in the notebook and reduced data (and
someday photometry!) will be yours.

Under the hood
==============

If you look at the source code you'll notice pretty quickly that there
is no actual *science* code. Think of this as the glue that brings
together a couple related packages:

-  `ccdproc <http://github.com/astropy/ccdproc>`__ for the actual data
   reduction.
-  `astropy <http://github.com/astropy>`__ for lots of the underlying
   structure .
