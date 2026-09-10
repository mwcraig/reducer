1.0.0 (unreleased)
------------------

General
^^^^^^^

New Features
^^^^^^^^^^^^

Other Changes
^^^^^^^^^^^^^

Bug fixes
^^^^^^^^^

0.8.3 (unreleased)
------------------

General
^^^^^^^

New Features
^^^^^^^^^^^^

- ``Combiner`` takes a ``mem_limit`` argument that sets the memory limit used
  when combining images. If it is not given the module-level
  ``reducer.astro_gui.DEFAULT_MEMORY_LIMIT`` is used.

Other Changes
^^^^^^^^^^^^^

- Combining images uses much less memory. The combined image is accumulated
  in the dtype chosen by ``REDUCE_IMAGE_DTYPE_MAPPING`` (float32 for data
  originating as 8- or 16-bit integers, float64 otherwise) instead of always
  in float64, the mask and uncertainty that ccdproc generates are discarded
  as soon as combining is done if the input images have neither, only the
  header of one input image is read instead of the whole image, and sigma
  clipping uses astropy's ``median`` and ``mad_std`` selected by name through
  ccdproc instead of the slower, higher memory defaults. The remaining fixed
  memory cost inside ``ccdproc.combine`` is reported in
  https://github.com/astropy/ccdproc/issues/1012.

- Combining raw integer frames (e.g. uint16) now produces a float32 master
  instead of casting the result back to the input integer type. Master files
  produced from raw frames are therefore about twice as large as before and
  are no longer integer-valued. Masters combined from already-reduced
  float32 frames are unchanged.

- ``DEFAULT_MEMORY_LIMIT`` is now 5e7 bytes instead of 1e9, and its
  documentation now describes what it actually controls. Peak memory while
  combining is roughly two to three times this limit plus the size of one
  output image.

- ``Combiner`` no longer keeps the most recently combined image in memory.
  The ``combined`` property now reads that image from disk each time it is
  accessed and is ``None`` until images have been combined.

- Reduction of an image is now done in the data type the reduced image will
  be written in rather than allowing ccdproc to promote the image to float64,
  and dark frames are scaled before subtraction rather than during it, which
  avoids the same promotion. Both roughly halve the memory needed to reduce
  an image. The promotion by ``ccdproc.subtract_dark`` is reported in
  https://github.com/astropy/ccdproc/issues/1013.

- Master calibration images are no longer kept in memory after a reduction
  finishes; they are re-read the next time a reduction is run.

- The template notebook's directory chooser now uses ``ipyfilechooser``
  instead of ``ipyautoui``, saving roughly 85 MB of kernel memory per
  notebook.

- ``FitsViewer`` in the image browser no longer keeps the displayed image
  array in memory.

Bug fixes
^^^^^^^^^

0.7.0 (2024-02-13)
------------------

General
^^^^^^^

New Features
^^^^^^^^^^^^

- Support several exposure time keyword names.

Other Changes
^^^^^^^^^^^^^

Bug fixes
^^^^^^^^^


0.6.0 (2024-02-13)
------------------

General
^^^^^^^

New Features
^^^^^^^^^^^^

- Support non-IRAF image types. [#177]

Other Changes
^^^^^^^^^^^^^

Bug fixes
^^^^^^^^^


0.5.1 (2023-09-13)
------------------

General
^^^^^^^

New Features
^^^^^^^^^^^^

Other Changes
^^^^^^^^^^^^^

Bug fixes
^^^^^^^^^

- If there is a single image in a group in the image browser the name
  of the image is now selectable. [#176]

0.3.0 (2016-07-17)
------------------

General
^^^^^^^

- This version only supports IPython 4 or higher, and requires ``ipywidgets`` version 4.
- The minimum required version of ccdproc is now 1.0.

New Features
^^^^^^^^^^^^

- Images can now simply be copied from the source to the destination directory. [#137]

Other Changes
^^^^^^^^^^^^^

Bug fixes
^^^^^^^^^


0.2.9 (2016-06-16)
------------------

General
^^^^^^^

New Features
^^^^^^^^^^^^

Other Changes
^^^^^^^^^^^^^

- Update package requirements to ipywidgets instead of ipython, and restrict
  version number.

Bug fixes
^^^^^^^^^

- Use numpy dtype name instead of dtype itself to determine output
  dtype. [#129]


0.2.8 (2016-05-31)
------------------

General
^^^^^^^

New Features
^^^^^^^^^^^^

Other Changes
^^^^^^^^^^^^^

Bug fixes
^^^^^^^^^

- Check that the image collection for master images exists before refreshing
  it. [#128]

0.2.7 (2016-05-30)
------------------

General
^^^^^^^

New Features
^^^^^^^^^^^^

Other Changes
^^^^^^^^^^^^^

Bug fixes
^^^^^^^^^

- The `ImageFileCollection` used to find masters was out of date and not
  refreshed if a reduction widget was created before the masters were
  created. [#127]

0.2.6 (2016-05-27)
------------------

General
^^^^^^^

New Features
^^^^^^^^^^^^

Other Changes
^^^^^^^^^^^^^

- Use combine function for combining images to limit memory usage during
  image combination. [#120, #121]

- Use ``median`` and ``median_absolute_deviation`` in sigma clipping instead
  of the default ``mean`` and ``std``. [#106]

- Discard mask/uncertainty from result of image combination unless input
  images have mask/uncertainty. [#119]

- Choose sensible data type for reduced images based on data type of original
  images. [#122]

Bug fixes
^^^^^^^^^

- Eliminate huge memory usage by reduction. [#118]


0.2.5 (2016-05-25)
------------------

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
------------------

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
