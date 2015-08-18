.. _use_with_students:

Using with reducer with students
================================

*Disclaimer*: My experience using `reducer`_ is with undergraduates, primarily
physics majors. It has been used by a couple of non-majors with no issues.

The first hurdle is installation and a really fast intro to the terminal on
the platform of their choice, since you need to launch a jupyter (nee ipython)
notebook from the terminal.

For installation and set up I point them to a set of notes about
`the mechanics of getting started`_.

I then have them walk through the notebook using the small dataset included
with the notebook. This is data that I've reduced by two in each image
dimension and converted from 16 bit to 8 bit. It is fine for learning how to
use the notebook, but the reduced data will look awful because I was not very
careful about converting the calibration images.

If you want the same data set, but at original resolution and 16-bit,
`download it here`_ (WARNING: 1.5GB). It is images of part of the Landolt
field SA112 SF1, taken over one night in July 2013 at the `Feder Observatory`_.
It covers a reasonably wide range of airmass, so can be used as
an example calculating atmospheric extinction and for determining the
transformation to the standard magnitude system. The images contain WCS
information, so it shouldn't be too hard to identify the Landolt stars.

.. _the mechanics of getting started: http://astro-research-setup.readthedocs.org/en/latest/
.. _Feder Observatory: http://astronomy.mnstate.edu/Feder_Observatory/
.. _download it here: http://physics.mnstate.edu/craig/2013-07-03.zip
.. _reducer: http://reducer.readthedocs.org/
