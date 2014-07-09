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


def load_image_click(b):
    """
    I am an awful function. I rely on load_progress being already defined
    outside my scope.

    If the person who wrote me was virtous I would be a method on a custom
    widget class. Obviously, he is not...
    """
    import time

    container = b.container
    container.load_progress.visible = True
    sleep_for = 0.001
    max_i = 2000
    for i in range(max_i):
        container.load_progress.value = i/max_i
        time.sleep(sleep_for)
    container.load_progress.visible = False
    container.status_label.value = "Done loading"
    container.status_label.add_class("alert")
    container.status_label.add_class("alert-success")
    container.status_label.visible = True
    time.sleep(1)
    container.status_label.visible = False


class LoadContainer(object):
    """docstring for LoadContainer"""
    def __init__(self):
        super(LoadContainer, self).__init__()
        self.load_container = \
            widgets.ContainerWidget(description="Hold file loading info")
        self.start_processing = \
            widgets.ButtonWidget(description="Load image info")
        # add container to the button object so it can introspect in the
        # on_click callback.
        self.start_processing.container = self
        self.start_processing.on_click(load_image_click)
        self.load_progress = widgets.FloatProgressWidget(min=0, max=1,
                                                         step=0.01, value=0,
                                                         description="Loading",
                                                         visible=False)
        self.status_label = widgets.LatexWidget(visible=False)
        self.load_container.children = [self.start_processing,
                                        self.load_progress,
                                        self.status_label]


class ImageSummary1(object):
    """docstring for ImageSummary1"""
    def __init__(self):
        super(ImageSummary1, self).__init__()
        self.image_summary = widgets.TabWidget(description="Summary container")
        image_types = ["Bias", "Dark", "Flat", "Light"]
        image_type_buttons = [widgets.TextareaWidget(description=t,
                                                     value="Nice long list of images")
                              for t in image_types]
        self.image_summary.children = image_type_buttons
        #self.image_summary.on_trait_change(self.set_tab_callback(), name="visible")

    def set_tab_names(self):
        for index, tab in enumerate(self.image_summary.children):
            self.image_summary.set_title(index, tab.description)

    def set_tab_callback(self):
        def tab_callback():
            return self.set_tab_names
        return tab_callback


class MakeMasterButtons(widgets.ContainerWidget):
    """docstring for MakeMasterButtons"""
    def __init__(self, calibration_types=None):
        super(MakeMasterButtons, self).__init__()
        if calibration_types is None:
            calibration_types = ["Bias", "Dark", "Flat"]
        buttons = \
            [widgets.ButtonWidget(description="Make Master {0}".format(c))
             for c in calibration_types]
        status_message = widgets.FloatProgressWidget(visible=False, min=0,
                                                     max=1, value=1)
        calib_container = widgets.ContainerWidget()
        calib_container.children = buttons
        for button in buttons:
            button.parent = calib_container
            button.on_click(self._change_my_color())
        calib_container.parent = self
        self.calib_container = calib_container
        self.children = [calib_container, status_message]

    def _change_my_color(self):
        def change_my_color(b):
            status_message = self.children[1]
            status_message.description = "Processing..."
            status_message.remove_class("progress-success")
            status_message.add_class(["progress", "progress-striped", "active"])
            status_message.visible = True
            import time; time.sleep(3)
            status_message.description = "Done!"
            status_message.remove_class(["progress-striped", "active"])
            status_message.add_class("progress-success")
            b.add_class('btn-success')
            b.description = "Made " + b.description[5:]
            time.sleep(2)
            status_message.visible = False
        return change_my_color

    def display(self):
        from IPython.display import display
        display(self)
        self.layout()

    def layout(self):
        self.calib_container.remove_class('vbox')
        self.calib_container.add_class('hbox')
        for button in self.calib_container.children:
            button.add_class('btn-warning')
            button.set_css('margin', '5px')


class ReduceContainer(widgets.ContainerWidget):
    """docstring for ReduceContainer"""
    def __init__(self):
        super(ReduceContainer, self).__init__()
        reduce_button = widgets.ButtonWidget(description="Reduce my data!")
        reduce_button.on_click(self._reduce_data())
        self.children = [reduce_button]

    def _reduce_data(self):
        def reduce_data(b):
            import time
            original_description = b.description
            b.description = "Just kidding"
            time.sleep(1)
            b.description = original_description
        return reduce_data

    def display(self):
        from IPython.display import display
        display(self)
        self.set_css({'width': '100%'})
        button = self.children[0]
        button.add_class("btn-block")


def show_images(button):
    images = button.parent.image_list
    num = len(images)

    def view_image(i):
        plt.imshow(images[i])
        plt.title("Image {0}".format(i))
        plt.show()
    widgets.interact(view_image, i=(0, num - 1))


class ImageDisplayStuff(widgets.ContainerWidget):
    """docstring for ImageDisplayStuff"""
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

        old : IPython.widget
            Child to be replaced

        new : IPython widget or None
            Replacement child (or None)

        Children are stored as a tuple so they are immutable.
        """
        current_children = list(parent.children)
        for idx, child in enumerate(current_children):
            if child is old:
                current_children[idx] = new
        parent.children = current_children

    def _create_gui(self):
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
        from IPython.display import display
        display(self._top)
        self.format()

    def format(self):
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
        from IPython.display import display
        display(self._top)
        self.format()

    def format(self):
        self._top.set_title(0, 'Image')
        self._top.set_title(1, 'Header')
        self._top.set_css('width', '100%')
        self._header_display.set_css('width', '50%')

    def _set_fits_file_callback(self):
        def set_fits_file(name, fits_file):
            import random
            place_holder_files = ['flood-flat-001R.fit', 'SA112-SF1-001R1.fit']
            use_file = random.choice(place_holder_files)
            full_path = os.path.join(get_data_path(), use_file)
            with fits.open(full_path) as hdulist:
                hdu = hdulist[0]
                self._data = hdu.data
                self._header = hdu.header
            self._header_display.value = repr(self._header)
            self._image.value = ndarray_to_png(self._data)
            self.top.visible = True

        return set_fits_file


class ImageBrowserWidget(widgets.ContainerWidget):
    """docstring for ImageBrowserWidget"""
    def __init__(self, tree, *args, **kwd):
        super(ImageBrowserWidget, self).__init__(*args, **kwd)
        self._tree_widget = ImageTreeWidget(tree)
        self._fits_display = FitsViewerWidget()
        self._fits_display.top.visible = False
        self.children = [self.tree_widget, self.fits_display]
        # Connect the select boxes to the image displayer
        self._add_handler(self.tree_widget)

    @property
    def tree_widget(self):
        return self._tree_widget.top

    @property
    def fits_display(self):
        return self._fits_display.top

    def display(self):
        from IPython.display import display
        display(self)
        self.format()

    def format(self):
        self.remove_class('vbox')
        self.add_class('hbox')
        self._tree_widget.format()
        self._fits_display.format()
        self.tree_widget.set_css('width', '40%')

    def _add_handler(self, node):
        if isinstance(node, widgets.SelectWidget):
            node.on_trait_change(self._fits_display._set_fits_file_callback(),
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
    Notes
    -----

    Do *NOT* set the children of the ToggleContainerWidget; set the children
    of ToggleContainerWidget.children
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
        self.children = [self._toggle_container, self._container]
        self._container.on_trait_change(self._link_children, str('_children'))

    @property
    def container(self):
        return self._container

    @property
    def toggle(self):
        return self._checkbox

    def _link_children(self):
        from IPython.utils.traitlets import link
        child_tuples = [(child, str('visible')) for child
                        in self._container.children]
        if child_tuples:
            child_tuples.insert(0, (self._checkbox, str('value')))
            link(*child_tuples)

    def format(self):
        self._toggle_container.set_css('padding', '3px')
        self.container.set_css('padding', '0px 0px 0px 30px')
        #self.container.set_css('border', '1px red solid')
        #self._toggle_container.set_css('border', '1px red solid')
        self._toggle_container.remove_class('start')
        self._toggle_container.add_class('center')


class ToggleMinMaxWidget(ToggleContainerWidget):
    def __init__(self, *args, **kwd):
        super(ToggleMinMaxWidget, self).__init__(*args, **kwd)
        min_box = widgets.FloatTextWidget(description="Low threshold")
        max_box = widgets.FloatTextWidget(description="High threshold")
        self.container.children = [min_box, max_box]

    def format(self):
        super(ToggleMinMaxWidget, self).format()
        hbox_these = [self, self.container]
        for hbox in hbox_these:
            hbox.remove_class('vbox')
            hbox.add_class('hbox')


class CombinerWidget(ToggleContainerWidget):
    """
    Widget for displaying options for ccdproc.Combiner.

    Parameters
    ----------

    description : str, optional
        Text displayed next to check box for selecting options.
    """
    def __init__(self, *args, **kwd):
        super(CombinerWidget, self).__init__(*args, **kwd)
        self._clipping_widget = \
            ToggleContainerWidget(description="Clip before combining?")
        min_max = ToggleMinMaxWidget(description="Clip by min/max?")
        sigma_clip = ToggleMinMaxWidget(description="Sigma clip?")
        self._clipping_widget.container.children = [min_max, sigma_clip]
        self._combine_method = \
            widgets.ToggleButtonsWidget(description="Combination method:",
                                        values=[
                                            'None',
                                            'Average',
                                            'Median'
                                        ])

        self.container.children = [self._clipping_widget, self._combine_method]
        self.min_max = min_max
        self.sigma_clip = sigma_clip

    def display(self):
        from IPython.display import display
        display(self)
        self.format()

    def format(self):
        super(CombinerWidget, self).format()
        self._clipping_widget.format()
        self.container.set_css({'border': '1px grey solid', 'border-radius': '10px'})
        self.min_max.format()
        self.sigma_clip.format()
        self._toggle_container.set_css('width', '100%')
        self._checkbox.set_css('width', '100%')
