This package provides an ipython notebook for reducing and doing
stellar photometry on CCD data.

New to python? Start here
=========================

Getting started with python can be intimidating; if you have questions please
`contact me <mailto:mcraig@mnstate.edu>`_!

To actually run this tool you need to install the 
`anaconda python distribution <http://continuum.io/downloads>`_. It will
*not* interfere in any way with other python installations you have.

Please provide feedback
=======================

Comments are very, very much welcome. Please comment by `making a new
issue on Github <https://github.com/mwcraig/reducer/issues>`__ (if, by
chance, a reasonably senior academic is using this, you can send
feedback by email; anyone else should *really* create a github account
so you can make an issue :)).

Installation
============

You need python (2.7, or 3.4 or higher) and the `SciPy
stack <http://scipy.org>`__. The easiest way to the get the full stack
is from a distribution like `anaconda <http://continuum.io>`__.

Then, in a terminal/command window:

::

    pip install --pre reducer


You can, if you want, grab the source on github (there is a "Download as
ZIP" link on the right you can use if you don't want to mess git),
change into the source directory, and run ``python setup.py install``.

Usage
=====

This package doesn't magically do your reduction for you. Instead, it
creates a template `ipython notebook <http://ipython.org>`_ that leads
you through data reduction and aperture photometry. When you are done
you have reduced your data and *you have a notebook that allows you or
someone else to reproduce your work*.

In a terminal, navigate to the directory where you want to keep the
notebook for doing your reduction (which does not have to be the same
directory where the data is, though it can be), then type::

    reducer

This will create a new template notebook. To open the notebook, type
in a terminal::

    ipython notebook

A browser window will open; the notebook you want is named "reduction.ipynb".
Click on it, then just do what it says in the notebook and reduced data (and
someday photometry!) will be yours.

Under the hood
==============

If you look at the source code you'll notice pretty quickly that there
is no actual *science* code. Think of this as the glue that brings
together a few related packages:

-  `ccdproc <http://github.com/astropy/ccdproc>`__ for the actual data
   reduction.
-  `photutils <http://github.com/astropy/photutils>`__ for photometry.
-  `astropy <http://github.com/astropy>`__ for lots of the underlying
   structure .

