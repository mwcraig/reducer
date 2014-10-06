from __future__ import (division, print_function, absolute_import,
                        unicode_literals)
from collections import OrderedDict
import os
from io import BytesIO

from IPython.html import widgets
import matplotlib.pyplot as plt
import numpy as np

from astropy.io import fits

import msumastro

from .notebook_dir import get_data_path

__all__ = [
    'LoadContainer',
    'ImageDisplayStuff',
    'ImageTreeWidget',
    'FitsViewerWidget',
    'ImageBrowserWidget',
    'ToggleContainerWidget',
    'ToggleMinMaxWidget',
    'ToggleGoWidget',
    'show_images',
    'ndarray_to_png',
    'set_color_for',
]


class LoadContainer(widgets.ContainerWidget):
    """
    Widget for loading a collection of FITS files

    Parameters
    ----------

    data_dir : str
        DIrectory in which the data is located.
    """
    def __init__(self, *args, **kwd):
        data_directory = kwd.pop('data_dir', None)
        super(LoadContainer, self).__init__(*args, **kwd)
        self.description = "Hold file loading info"
        self.button = \
            widgets.ButtonWidget()
        # add container to the button object so it can introspect in the
        # on_click callback.

        # REPLACE THIS WITH A CLOSURE
        self.button.container = self

        self.load_progress = widgets.FloatProgressWidget(min=0, max=1,
                                                         step=0.01, value=1,
                                                         description="Loading",
                                                         visible=False)
        self.status_label = widgets.LatexWidget(visible=False)
        self.children = [self.button,
                         self.load_progress,
                         self.status_label]

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

        Must be called after the widget is displayed, and is automatically called
        by the `display` method.
        """
        self.remove_class('vbox')
        self.add_class('hbox')
        self.add_class('align-center')
        self.set_css('width', '100%')
        self.button.add_class('btn-info')
        self.button.set_css('width', '50%')

    def start_progress(self):
        """
        Change state of progress bar to indicate beginning of operation.
        """
        self.load_progress.visible = True
        self.load_progress.description = "Loading"
        self.load_progress.remove_class("progress-success")
        self.load_progress.add_class(["progress", "progress-striped", "active"])
        self.button.disabled = True
        self.button.set_css('width', '25%')

    def end_progress(self):
        """
        Change state of progress bar to indicate end of operation.
        """
        self.load_progress.description = "Done!"
        self.load_progress.remove_class(["progress-striped", "active"])
        self.load_progress.add_class("progress-success")
        self.button.disabled = False


def show_images(button):
    """
    Do a quick and dirty plot of an image.

    Parameters
    ----------

    button : `IPython.html.widgets.ButtonWidget`
        Button whose click generated this call.
    """
    images = button.parent.image_list
    num = len(images)

    def view_image(i):
        plt.imshow(images[i])
        plt.title("Image {0}".format(i))
        plt.show()
    widgets.interact(view_image, i=(0, num - 1))


class ImageDisplayStuff(widgets.ContainerWidget):
    """
    Widget to display a list of images with a slider.

    Parameters
    ----------

    image_list : list
        Images to be shown, as numpy arrays (or anything that can be
        display with `matplotlilb.plt.imshow`)
    """
    def __init__(self, image_list=None):
        super(ImageDisplayStuff, self).__init__()
        if image_list is None:
            image_list = []
        button = widgets.ButtonWidget(description='Show reduced images')
        button.parent = self
        self.children = [button]
        self.image_list = image_list
        button.on_click(show_images)

    def display(self):
        from IPython.display import display
        display(self)


class ImageTreeWidget(object):
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
        `IPython.html.widgets.AccordionWidget`, if the node has child nodes,
        or a `IPython.html.widgets.SelectWidget`, if the node has a list.

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
                self._top = widgets.AccordionWidget(description=key)
                self._gui_objects[parent_string] = self._top

            parent = self._gui_objects[parent_string]
            # Do I have a children? If so, add them as tabs
            if children:
                child_objects = []
                for child in children:
                    desc = ": ".join([key, str(child)])
                    child_container = widgets.AccordionWidget(description=desc)
                    child_container.parent = self._gui_objects[parent_string]
                    child_string = os.path.join(parent_string, str(child))
                    self._gui_objects[child_string] = child_container
                    child_objects.append(child_container)
                parent.children = child_objects
            # Do I have only a list? Populate a select box with those...
            if index:
                new_text = widgets.SelectWidget(values=index)
                index_string = self._id_string([parent_string, 'files'])
                self._gui_objects[index_string] = new_text
                old_parent = parent
                grandparent = old_parent.parent
                desc = old_parent.description
                s_or_not = ['', 's']
                n_files = len(index)
                desc += " ({0} image{1})".format(n_files,
                                                 s_or_not[n_files > 1])
                parent = widgets.ContainerWidget(description=desc)
                parent.children = [new_text]
                parent.parent = grandparent
                self._replace_child(grandparent, old=old_parent, new=parent)

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
        #self._top.set_css({'width': '50%'})
        for name, obj in self._gui_objects.iteritems():
            if isinstance(obj, widgets.AccordionWidget):
                for idx, child in enumerate(obj.children):
                    if not isinstance(child, widgets.SelectWidget):
                        obj.set_title(idx, child.description)


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
    x = np.asarray(Image.fromarray(x).resize(new_shape))
    x = (x - x.mean()) / x.std()
    x[x >= 3] = 2.99
    x[x < -3] = -3.0
    x = (x - x.min()) / (1.1*x.max() - x.min())
    img = Image.fromarray((x*256).astype('uint8'))
    img_buffer = BytesIO()
    img.save(img_buffer, format='png')
    return img_buffer.getvalue()


class FitsViewerWidget(object):
    """
    Display the image and header from a single FITS file.


    """
    def __init__(self):
        self._top = widgets.TabWidget(visible=False)
        self._data = None  # hdu.data
        self._png_image = None  # ndarray_to_png(self._data)
        self._header = ''
        self._image = widgets.ImageWidget()
        self._header_display = widgets.TextareaWidget(disabled=True)
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
        self._header_display.set_css('height', '300px')

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


class ImageBrowserWidget(widgets.ContainerWidget):
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
        super(ImageBrowserWidget, self).__init__(*args, **kwd)
        self._tree_widget = ImageTreeWidget(tree)
        self._fits_display = FitsViewerWidget()
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
        self.remove_class('vbox')
        self.add_class('hbox')
        self.set_css('width', '100%')
        self._tree_widget.format()
        self._fits_display.format()
        self.tree_widget.add_class('box-flex1')
        self.fits_display.add_class('box-flex2')
        for child in self.children:
            child.set_css('margin', '10px')

    def _add_handler(self, node):
        if isinstance(node, widgets.SelectWidget):
            node.on_trait_change(
                self._fits_display.set_fits_file_callback(demo=self._demo,
                                                          image_dir=self._directory),
                str('value'))
            return
        if hasattr(node, 'children'):
            for child in node.children:
                self._add_handler(child)


class ToggleContainerWidget(widgets.ContainerWidget):
    """
    A widget whose state controls the visibility of its chilren.

    Parameters
    ----------

    Same as parameters for a `~IPython.html.widgets.ContainerWidget`, but
    note that the description of the ToggleContainerWidget is used to set the
    description of the checkbox that controls the display, AND

    toggle_type : {'checkbox', 'button'}, optional
        Specify the type of boolean widget used to toggle the display

    Attributes
    ----------

    container : ContainerWidget
        Object to which children should be added.

    toggle : ToggleButtonWidget or CheckboxWidget
        The toggle object, provided primarily to allow styling of it.

    disabled : bool
        Gets and sets whether the entire widget is disabled, i.e. the toggle
        box and all children of this widget controlled by the toggle.

    Notes
    -----

    Do *NOT* set the children of the ToggleContainerWidget; set the children
    of ``ToggleContainerWidget.children`` or use the `add_child` method.
    """
    def __init__(self, *args, **kwd):
        toggle_types = {'checkbox': widgets.CheckboxWidget,
                        'button': widgets.ToggleButtonWidget}
        toggle_type = kwd.pop('toggle_type', 'checkbox')
        if toggle_type not in toggle_types:
            raise ValueError('toggle_type must be one of '
                             '{}'.format(toggle_type.keys()))
        super(ToggleContainerWidget, self).__init__(*args, **kwd)
        self._toggle_container = widgets.ContainerWidget(description='toggle holder')
        self._checkbox = toggle_types[toggle_type](description=self.description)
        self._toggle_container.children = [self._checkbox]
        self._container = widgets.ContainerWidget(description="Toggle-able container")
        self._state_monitor = widgets.CheckboxWidget(visible=False)

        self.children = [
            self._toggle_container,
            self._container,
            self._state_monitor
        ]

        self._link_children()
        self._child_notify_parent_on_change(self.toggle)

    def __str__(self):
        # Build up a list of strings of top level and children
        yes_no = lambda x: 'Yes' if x else 'No'
        base = ' '.join([self.description, yes_no(self.toggle.value)])
        if self.toggle.value:
            child_strings = ['\t' + str(child) for child in self.container.children]
            indented_kids = [s.replace('\n\t', '\n\t\t') for s in child_strings]
            base += '\n' + '\n'.join(indented_kids)
        return base

    @property
    def container(self):
        """
        Widget that contains the elements controlled by the toggle.
        """
        return self._container

    @property
    def toggle(self):
        """
        Toggle widget that controls other display elements.
        """
        return self._checkbox

    def _link_children(self):
        """
        Links the visible property of the container to the toggle value.
        """
        from IPython.utils.traitlets import link
        link((self._checkbox, str('value')), (self._container, str('visible')))

    @property
    def disabled(self):
        """
        True if widget is disabled.
        """
        return self._state_monitor.disabled

    @disabled.setter
    def disabled(self, value):
        # Not every widget has a disabled attribute (e.g. ContainerWidget),
        # but we can go down through children recursively if needed.
        def set_disabled(child, value):
            if hasattr(child, 'disabled'):
                child.disabled = value
            elif hasattr(child, 'children'):
                for grandkid in child.children:
                    set_disabled(grandkid, value)

        # someday test for boolean in here....
        self._state_monitor.disabled = value
        self.toggle.disabled = value
        for child in self.container.children:
            set_disabled(child, value)

    @property
    def is_sane(self):
        """
        Subclasses can define a method that indicates whether the
        current combination of settings is sensible.

        Returns
        -------

        sanity : bool or None
            True if the settings are sensible, False if not, None if not
            overridden.
        """
        return None

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
        self._toggle_container.set_css('padding', '3px')
        self.container.set_css('padding', '0px 0px 0px 30px')
        #self.container.set_css('border', '1px red solid')
        #self._toggle_container.set_css('border', '1px red solid')
        self._toggle_container.remove_class('start')
        self._toggle_container.add_class('center')

    def add_child(self, child):
        """
        Append a child to the container part of the widget.

        Parameters
        ----------

        child : IPython widget
        """
        temp = list(self.container.children)
        temp.append(child)
        self.container.children = temp
        self._child_notify_parent_on_change(child)

    def action(self):
        """
        Subclasses should override this method if they wish to associate an
        action with the widget.
        """
        pass

    def _child_notify_parent_on_change(self, child):
        # For some reason DropdownWidgets do not have a value key, only a
        # value_name key. Seems inconsistent with the rest of the
        # widgets, but whatever...

        if isinstance(child, ToggleContainerWidget):
            # If the child is a ToggleContainerWidget we only need to link in
            # to its _state_monitor because it will take care hooking up the
            # things in the container to its _state_monitor.
            child._state_monitor.on_trait_change(self._ping_handler(),
                                                 str('value'))
        elif str('value') in child.traits():
            # If the child has a value trait we want to monitor it.
            child.on_trait_change(self._ping_handler(), str('value'))
        else:
            # Might be a plain ContainerWidget (or tab or accordion), so look
            # for its children.
            try:
                for grandchild in child.children:
                    self._child_notify_parent_on_change(grandchild)
            except AttributeError:
                pass

    def _ping_handler(self):
        def flip_state():
            self._state_monitor.value = not self._state_monitor.value

        return flip_state


class ToggleMinMaxWidget(ToggleContainerWidget):
    """
    Widget for setting a minimum and maximum integer value, controlled by
    a toggle.

    Parameters
    ----------

    description : str
        Text to be displayed in the toggle.
    """
    def __init__(self, *args, **kwd):
        super(ToggleMinMaxWidget, self).__init__(*args, **kwd)
        self._min_box = widgets.FloatTextWidget(description="Low threshold")
        self._max_box = widgets.FloatTextWidget(description="High threshold")
        self.add_child(self._min_box)
        self.add_child(self._max_box)

    def format(self):
        super(ToggleMinMaxWidget, self).format()
        hbox_these = [self, self.container]
        for hbox in hbox_these:
            hbox.remove_class('vbox')
            hbox.add_class('hbox')
        for child in self.container.children:
            child.set_css('width', '30px')

    @property
    def min(self):
        """
        Minimum value in the widget.
        """
        return self._min_box.value

    @property
    def max(self):
        """
        Maximum value in the widget.
        """
        return self._max_box.value

    def __str__(self):
        # Build up a list of strings of top level and children
        yes_no = lambda x: 'Yes' if x else 'No'
        base = ' '.join([self.description, yes_no(self.toggle.value)])
        if self.toggle.value:
            child_strings = ['\t' + str(child.description) + ': ' + str(child.value) for child in self.container.children]
            indented_kids = [s.replace('\n\t', '\n\t\t') for s in child_strings]
            base += '\n' + '\n'.join(indented_kids)
        return base

class ToggleGoWidget(ToggleContainerWidget):
    """
    ToggleContainerWidget whose state is linked to a button.

    The intent is for that button to be activated when the contents
    of the container are in a "sane" state.
    """
    def __init__(self, *args, **kwd):
        from IPython.utils.traitlets import link

        super(ToggleGoWidget, self).__init__(*args, **kwd)
        self._go_container = widgets.ContainerWidget(visible=self.toggle.value)
        self._go_button = widgets.ButtonWidget(description="Lock settings and Go!",
                                               disabled=True, visible=False)
        self._change_settings = widgets.ButtonWidget(description="Unlock settings",
                                                     disabled=True,
                                                     visible=False)
        self._go_container.children = [self._go_button, self._change_settings]
        self._progress_container = widgets.ContainerWidget()
        self._progress_bar = widgets.FloatProgressWidget(min=0, max=1.0,
                                                         step=0.01, value=0.0,
                                                         visible=False)
        self._progress_container.children = [self._progress_bar]
        # we want the go button to be in a container below the
        #  ToggleContainer's container -- actually, no, want these
        # buttons controlled by toggle...wait, no, I really do want that, but
        # I also want to tie their visibility to the toggle.
        kids = list(self.children)
        kids.append(self._go_container)
        kids.append(self._progress_container)
        self.children = kids

        # Tie visibility of go button to toggle state. Needs to be separate
        # from the container.
        link((self._go_container, str('visible')), (self.toggle, str('value')))

        self._go_button.on_click(self.go())
        self._change_settings.on_click(self.unlock())

        # Tie self._state_monitor to both go button and color of toggle button
        self._state_monitor.on_trait_change(self.state_change_handler(),
                                            str('value'))
        self._state_monitor.on_trait_change(set_color_for(self), str('value'))

    def format(self):
        """
        Format the widget; must be invoked after displaying the widget.
        """
        super(ToggleGoWidget, self).format()
        for child in self.container.children:
            try:
                child.format()
            except AttributeError:
                pass
        #self._clipping_widget.format()
        self.container.set_css({'border': '1px grey solid',
                                'border-radius': '10px'})
        self._toggle_container.set_css('width', '100%')
        self._checkbox.set_css('width', '100%')
        self._go_container.remove_class('vbox')
        self._go_container.add_class('hbox')
        self._go_container.set_css('padding', '5px')
        self._go_container.set_css('width', '100%')
        self._go_button.add_class('box-flex1')
        self._change_settings.add_class('box-flex3')
        self._go_button.add_class('btn-info')
        self._change_settings.add_class('btn-inverse')
        self._progress_container.set_css('width', '100%')
        self._progress_bar.add_class('progress-info')
        #self._progress_bar.set_css('width', '90%')
        for child in self._go_container.children:
            child.set_css('margin', '5px')

    @property
    def is_sane(self):
        # There are two ways to be insane here:

        # 1. No steps are selected
        for child in self.container.children:
            try:
                if child.toggle.value:
                    break
            except AttributeError:
                # The child isn't a toggle, apparently...
                pass
        else:
            # Reminder: this executes if the loop completes successfully,
            # i.e. none of the children are selected
            return False

        # 2. There is a combination of settings that doesn't make sense.
        mental_state = [child.is_sane for child
                        in self.container.children
                        if hasattr(child, 'is_sane')
                        and child.is_sane is not None]
        sanity = all(mental_state)
        return sanity

    @property
    def progress_bar(self):
        return self._progress_bar

    def state_change_handler(self):
        """
        Ties sanity state to go button controls and others
        """
        def change_handler():
            if self.is_sane is None:
                return

            # Sorry about the double negative below, but the IPython widget
            # method is named DISabled...
            self._go_button.disabled = not self.is_sane
            self._go_button.visible = self.is_sane

        return change_handler

    def go(self):
        """
        Returns the action to be taken when the "Go" button is clicked.
        """
        def handler(b):
            """
            b is the button pressed
            """
            self.disabled = True
            self._go_button.disabled = True
            print(self)
            self.action()

            # change button should really only appear after the work is done.
            self._change_settings.visible = True
            self._change_settings.disabled = False
        return handler

    def unlock(self):
        """
        Handler for the unlock button.
        """
        def handler(b):
            self.disabled = False
            self._go_button.disabled = False
            self._change_settings.visible = False
        return handler


def set_color_for(a_widget):
    def set_color(name, value):
        if a_widget.toggle.value:
            if not a_widget.is_sane:
                a_widget.toggle.remove_class('btn-success')
                a_widget.toggle.add_class('btn-warning')
            else:
                a_widget.toggle.remove_class('btn-warning')
                a_widget.toggle.add_class('btn-success')
        else:
            a_widget.toggle.remove_class('btn-success')
            a_widget.toggle.remove_class('btn-warning')
    return set_color
