0.3.0 (unreleased)
----------------

General
^^^^^^^

New Features
^^^^^^^^^^^^

Other Changes
^^^^^^^^^^^^^

Bug fixes
^^^^^^^^^


0.2.6 (unreleased)
----------------

General
^^^^^^^

New Features
^^^^^^^^^^^^

Other Changes
^^^^^^^^^^^^^

Bug fixes
^^^^^^^^^

- Eliminate huge memory usage by reduction. [#118]


0.2.5 (2016-05-25)
----------------

General
^^^^^^^

New Features
^^^^^^^^^^^^

Other Changes
^^^^^^^^^^^^^

- Improve display of images in file browser.

Bug fixes
^^^^^^^^^

- Work around a bug in ccdproc/astropy.nddata that incorrectly creates an
  uncertainty as a mask.

- Work around a bug in astropy.io.fits that results in writing incorrect
  data values in some cases.

0.2.3 (2016-05-23)
----------------

General
^^^^^^^

New Features
^^^^^^^^^^^^

Other Changes
^^^^^^^^^^^^^

Bug fixes
^^^^^^^^^

- Ensure unsigned int images can be displayed. [#115, #116]
- Ensure that combined images can be written. [#117]
