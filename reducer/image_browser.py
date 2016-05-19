from __future__ import (division, print_function, absolute_import,
                        unicode_literals)

from collections import OrderedDict
import os
from io import BytesIO

import numpy as np

from astropy.io import fits
from astropy.extern import six

import msumastro

from .notebook_dir import get_data_path
from .ipython_version_helper import ipython_version_as_string

__all__ = [
    'ImageTree',
    'FitsViewer',
    'ImageBrowser',
    'ndarray_to_png',
]

ipython_version = ipython_version_as_string()

if ipython_version.startswith('3'):
    from IPython.html import widgets
    from IPython.utils.traitlets import Unicode
else:
    import ipywidgets as widgets
    from traitlets import Unicode

if (ipython_version.startswith('3') or
    (int(ipython_version) <= 402)):
    # Use my accordion js
    class Accordion(widgets.Accordion):

        _view_module = Unicode("nbextensions/accordion_replacement/accordion_patch", sync=True)
        _view_name = Unicode("AccordionView", sync=True)
else:
    class Accordion(widgets.Accordion):
        pass


class ImageTree(object):
    """
    Create a tree view of a collection of images.

    Parameters
    ----------

    tree : `msumastro.TableTree`
        Tree of images, arranged by metadata.
    """
    def __init__(self, tree):
        if not isinstance(tree, msumastro.TableTree):
            raise ValueError("argument must be a TableTree")
        self._tree = tree
        self._id_string = lambda l: os.path.join(*[str(s) for s in l]) if l else ''
        self._gui_objects = OrderedDict()
        self._top = None
        self._create_gui()
        self._set_titles()

    @property
    def top(self):
        """
        Widget at the top of the tree.
        """
        return self._top

    def _get_index_in_children(self, widget):
        parent = widget.parent
        for idx, wid in enumerate(parent.children):
            if widget is wid:
                return idx

    def _replace_child(self, parent, old=None, new=None):
        """
        Replace old child with new.

        Parameters
        ----------

        parent : IPython widget
            String that identifies parent in gui

        old : IPython widget
            Child to be replaced

        new : IPython widget or None
            Replacement child (or None)

        Notes
        -----

        Children are stored as a tuple so they are immutable.
        """
        current_children = list(parent.children)
        for idx, child in enumerate(current_children):
            if child is old:
                current_children[idx] = new
        parent.children = current_children

    def _create_gui(self):
        """
        Create the tree gui elements.

        Notes
        -----

        Each node of the tree is either an
        `IPython.html.widgets.Accordion`, if the node has child nodes,
        or a `IPython.html.widgets.Select`, if the node has a list.

        Note well this does **not** allow for the case of child nodes and
        a list, so this does not really suffice as a file browser.

        List nodes monkey with their parents by editing the description to
        include the number of list items in the node.
        """
        for parents, children, index in self._tree.walk():
            if children and index:
                # This should be impossible...
                raise RuntimeError("What the ???")
            parent_string = self._id_string(parents)
            depth = len(parents)
            try:
                key = self._tree.tree_keys[depth]
            except IndexError:
                key = ''
            if depth == 0:
                self._top = Accordion(description=key)
                self._top.selected_index = -1
                self._gui_objects[parent_string] = self._top

            parent = self._gui_objects[parent_string]

            # Do I have children? If so, add them as sub-accordions
            if children:
                child_objects = []
                for child in children:
                    desc = ": ".join([key, str(child)])
                    child_container = Accordion(description=desc)
                    # Make sure all panels start out closed.
                    child_container.selected_index = -1
                    child_container.parent = self._gui_objects[parent_string]
                    child_string = os.path.join(parent_string, str(child))
                    self._gui_objects[child_string] = child_container
                    child_objects.append(child_container)
                parent.children = child_objects
            # Do I have only a list? Populate a select box with those...
            if index:
                new_text = widgets.Select(options=index)
                index_string = self._id_string([parent_string, 'files'])
                self._gui_objects[index_string] = new_text

                # On the last pass an Accordion will have been created for
                # this item. We need to replace that Accordion with a Select.
                # The Select should be inside a box so that we can set a
                # description on the box that won't be displayed on the
                # Select. When titles are built for the image viewer tree
                # later on they are based on the description of the Accordions
                # and their immediate children.
                old_parent = parent
                grandparent = old_parent.parent
                desc = old_parent.description
                s_or_not = ['', 's']
                n_files = len(index)
                desc += " ({0} image{1})".format(n_files,
                                                 s_or_not[n_files > 1])

                # Place the box between the Select and the parent Accordion
                parent = widgets.Box(description=desc)
                parent.children = [new_text]
                parent.parent = grandparent
                self._replace_child(grandparent, old=old_parent, new=parent)

    def display(self):
        """
        Display and format this widget.
        """
        from IPython.display import display
        display(self._top)

    def _set_titles(self):
        """
        Set titles for accordions.

        This should apparently be done *before* the widget is displayed.
        """
        for name, obj in six.iteritems(self._gui_objects):
            if isinstance(obj, Accordion):
                for idx, child in enumerate(obj.children):
                    if not isinstance(child, widgets.Select):
                        obj.set_title(idx, child.description)

    def format(self):
        """
        This gets called by the ImageBrowser so don't delete it.
        """
        pass


def ndarray_to_png(x):
    from PIL import Image
    shape = np.array(x.shape)
    # Reverse order for reasons I do not understand...
    shape = shape[::-1]
    if len(shape) != 2:
        return
    aspect = shape[1]/shape[0]
    width = 600  # pixels
    new_shape = np.asarray(width/shape[0]*aspect*shape, dtype='int')
    x = np.asarray(Image.fromarray(x.astype('float32')).resize(new_shape))
    x = (x - x.mean()) / x.std()
    x[x >= 3] = 2.99
    x[x < -3] = -3.0
    x = (x - x.min()) / (1.1*x.max() - x.min())
    img = Image.fromarray((x*256).astype('uint8'))
    img_buffer = BytesIO()
    img.save(img_buffer, format='png')
    return img_buffer.getvalue()


class FitsViewer(object):
    """
    Display the image and header from a single FITS file.


    """
    def __init__(self):
        self._top = widgets.Tab(visible=False)
        self._data = None  # hdu.data
        self._png_image = None  # ndarray_to_png(self._data)
        self._header = ''
        self._image = widgets.Image()
        self._header_display = widgets.Textarea(disabled=True)
        self._top.children = [self._image, self._header_display]

    @property
    def top(self):
        return self._top

    def display(self):
        """
        Display and format this widget.
        """
        from IPython.display import display
        display(self._top)
        self.format()

    def format(self):
        """
        Format widget.

        Must be called after the widget is displayed, and is automatically
        called by the `display` method.
        """
        self._top.set_title(0, 'Image')
        self._top.set_title(1, 'Header')
        # self._header_display.set_css('height', '300px')
        self._header_display.height = '300px'

    def set_fits_file_callback(self, demo=True, image_dir=None):
        """
        Returns a callback function that sets the name of FITS file to
        display and updates the widget.

        The callback takes one argument, the name of the fits file, or 'demo'
        to enable the display of a couple of sample images.
        """
        def set_fits_file(name, fits_file):
            """
            Set image and header to a particular FITS file.

            Parameters
            ----------

            fits_file : str
                The name of the fits file, or 'demo' to enable the display of
                a couple of sample images.
            """
            if demo:
                import random
                place_holder_files = ['flood-flat-001R.fit',
                                      'SA112-SF1-001R1.fit']
                use_file = random.choice(place_holder_files)
                full_path = os.path.join(get_data_path(), use_file)
            else:
                if image_dir is not None:
                    full_path = os.path.join(image_dir, fits_file)
                else:
                    full_path = fits_file
            with fits.open(full_path) as hdulist:
                hdu = hdulist[0]
                self._data = hdu.data
                self._header = hdu.header
            self._header_display.value = repr(self._header)
            self._image.value = ndarray_to_png(self._data)
            self.top.visible = True

        return set_fits_file


class ImageBrowser(widgets.FlexBox):
    """
    Browse a tree of FITS images and view image/header.

    Parameters
    ----------

    tree : `msumastro.TableTree`
        Tree of images, arranged by metadata.
    """
    def __init__(self, tree, *args, **kwd):
        self._directory = kwd.pop('directory', '.')
        self._demo = kwd.pop('demo', True)
        kwd['orientation'] = 'horizontal'
        super(ImageBrowser, self).__init__(*args, **kwd)
        self._tree_widget = ImageTree(tree)
        self._fits_display = FitsViewer()
        self._fits_display.top.visible = False
        self.children = [self.tree_widget, self.fits_display]
        # Connect the select boxes to the image displayer
        self._add_handler(self.tree_widget)

    @property
    def tree_widget(self):
        """
        Widget that represents the image tree.
        """
        return self._tree_widget.top

    @property
    def fits_display(self):
        """
        Widget that displays FITS image/header.
        """
        return self._fits_display.top

    def display(self):
        """
        Display and format this widget.
        """
        from IPython.display import display
        display(self)
        self.format()

    def format(self):
        """
        Format widget.

        Must be called after the widget is displayed, and is automatically
        called by the `display` method.
        """
        # self.set_css('width', '100%')
        self.width = '100%'

        self._tree_widget.format()
        self._fits_display.format()

        # self.tree_widget.add_class('box-flex1')
        self.tree_widget.width = '20em'
        # self.fits_display.add_class('box-flex2')
        self.fits_display.width = '67%'
        for child in self.children:
            # child.set_css('margin', '10px')
            child.margin = '10px'

    def _add_handler(self, node):
        if isinstance(node, widgets.Select):
            node.on_trait_change(
                self._fits_display.set_fits_file_callback(demo=self._demo,
                                                          image_dir=self._directory),
                str('value'))
            return
        if hasattr(node, 'children'):
            for child in node.children:
                self._add_handler(child)
