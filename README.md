This "package" provides an ipython notebook for reducing and doing stellar
photometry on CCD data.

# Installation

You need python (2.7, or 3.4 or higher) and the [SciPy
stack](http://scipy.org). The easiest way to the get the full stack is from a
distribution like [anaconda](http://continuum.io).

Once you have that, just:

```
pip install --use-wheels reducer
```

You can, if you want, clone from the source on github and run ``python
setup.py install``.

# Usage

This package doesn't magically do your reduction for you. Instead, it creates
a template [ipython notebook](http://ipython.org) that leads you through data
reduction and aperture photometry. When you are done you have reduced your
data and *you have a notebook that allows you or someone else to reproduce
your work*.

Don't use the same notebook for multiple nights. 

In a terminal, navigate to the directory where you want to keep the notebook
for doing your reduction (which does not have to be the same directory where
the data is, though it can be), then type:

```
reducer
```

This will create a new template notebook and launch the notebook in a browser window; just do what it says in the notebook and reduced data (and photometry!) will be yours.

# Under the hood

If you look at the source code you'll notice pretty quickly that there is no actual *science* code. Think of this as the glue that brings together a few related packages:

+ [ccdproc](http://github.com/astropy/ccdproc) for the actual data reduction.
+ [photutils](http://github.com/astropy/photutils) for photometry.
+ [astropy](http://github.com/astropy) for lots of the underlying structure .
