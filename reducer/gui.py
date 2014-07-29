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
    'MakeMasterButtons',
    'ReduceContainer',
    'ImageDisplayStuff',
    'ImageTreeWidget',
    'FitsViewerWidget',
    'ImageBrowserWidget',
    'ToggleContainerWidget',
    'ToggleMinMaxWidget',
    'CombinerWidget',
    'CosmicRaySettingsWidget',
    'SliceWidget',
    'OverscanWidget',
    'CalibrationStepWidget',
    'ReductionSettings',
    'show_images',
    'ndarray_to_png',
    'set_color_for',
]


class LoadContainer(widgets.ContainerWidget):
    """docstring for LoadContainer"""
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
        from IPython.display import display
        display(self)
        self.format()

    def format(self):
        self.remove_class('vbox')
        self.add_class('hbox')
        self.add_class('align-center')

    def start_progress(self):
        self.load_progress.visible = True
        self.load_progress.description = "Loading"
        self.load_progress.remove_class("progress-success")
        self.load_progress.add_class(["progress", "progress-striped", "active"])

    def end_progress(self):
        self.load_progress.description = "Done!"
        self.load_progress.remove_class(["progress-striped", "active"])
        self.load_progress.add_class("progress-success")


class MakeMasterButtons(widgets.ContainerWidget):
    """docstring for MakeMasterButtons"""
    def __init__(self, calibration_types=None, bias=None):
        super(MakeMasterButtons, self).__init__()
        settings = {}
        if bias is not None:
            settings["Bias"] = bias
        if calibration_types is None:
            calibration_types = ["Bias", "Dark", "Flat"]
        buttons = \
            [widgets.ButtonWidget(description="Make Master {0}".format(c))
             for c in calibration_types]
        status_message = widgets.FloatProgressWidget(visible=False, min=0,
                                                     max=1, value=1)
        calib_container = widgets.ContainerWidget()
        calib_container.children = buttons
        for calib_name, button in zip(calibration_types, buttons):
            button.parent = calib_container
            button.on_click(self._change_my_color(settings=settings["Bias"]))
        calib_container.parent = self
        self.calib_container = calib_container
        self.children = [calib_container, status_message]

    def _change_my_color(self, settings=None):
        def change_my_color(b):
            status_message = self.children[1]
            if settings is not None:
                print(settings)
            status_message.description = "Processing..."
            status_message.remove_class("progress-success")
            status_message.add_class(["progress", "progress-striped", "active"])
            status_message.visible = True
            import time; time.sleep(1)
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
        self.set_css({'width': '60%'})
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

    action : callable or str
        An action associated with the widget. Can be either a callable
        (e.g. a function) or a string. This widget does *nothing* with
        the action; it is provided as a hook for controller code.

    disabled : bool
        Gets and sets whether the entire widget is disabled, i.e. the toggle
        box and all children of this widget controlled by the toggle.

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
        self._state_monitor = widgets.CheckboxWidget(visible=False)

        self.children = [
            self._toggle_container,
            self._container,
            self._state_monitor
        ]

        self._link_children()
        self._child_notify_parent_on_change(self.toggle)
        self.action = None

    @property
    def container(self):
        return self._container

    @property
    def toggle(self):
        return self._checkbox

    def _link_children(self):
        from IPython.utils.traitlets import link
        link((self._checkbox, str('value')), (self._container, str('visible')))

    @property
    def disabled(self):
        return self._state_monitor.disabled

    @disabled.setter
    def disabled(self, value):
        # someday test for boolean in here....
        self._state_monitor.disabled = value
        self.toggle.disabled = value
        for child in self.container.children:
            child.disabled = value

    def display(self):
        from IPython.display import display
        display(self)
        self.format()

    def format(self):
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

    def _child_notify_parent_on_change(self, child):
        child.on_trait_change(self._ping_handler(), str('value'))

    def _ping_handler(self):
        def flip_state():
            self._state_monitor.value = not self._state_monitor.value
        return flip_state


class ToggleMinMaxWidget(ToggleContainerWidget):
    def __init__(self, *args, **kwd):
        super(ToggleMinMaxWidget, self).__init__(*args, **kwd)
        min_box = widgets.FloatTextWidget(description="Low threshold")
        max_box = widgets.FloatTextWidget(description="High threshold")
        self.add_child(min_box)
        self.add_child(max_box)

    def format(self):
        super(ToggleMinMaxWidget, self).format()
        hbox_these = [self, self.container]
        for hbox in hbox_these:
            hbox.remove_class('vbox')
            hbox.add_class('hbox')
        for child in self.container.children:
            child.set_css('width', '30px')


class ToggleGoWidget(ToggleContainerWidget):
    """docstring for ToggleGoWidget"""
    def __init__(self, *args, **kwd):
        from IPython.utils.traitlets import link

        super(ToggleGoWidget, self).__init__(*args, **kwd)
        self._go_container = widgets.ContainerWidget(visible=self.toggle.value)
        self._go_button = widgets.ButtonWidget(description="Lock settings and Go!",
                                               disabled=True)
        self._change_settings = widgets.ButtonWidget(description="Unlock settings",
                                                     disabled=True,
                                                     visible=False)
        self._go_container.children = [self._go_button, self._change_settings]
        # we want the go button to be in a container below the
        #  ToggleContainer's container -- actually, no, want these
        # buttons controlled by toggle...wait, no, I really do want that, but
        # I also want to tie their visibility to the toggle.
        kids = list(self.children)
        kids.append(self._go_container)
        self.children = kids

        # Tie visibility of go button to toggle state. Needs to be separate
        # from the container.
        link((self._go_container, str('visible')), (self.toggle, str('value')))

        self._go_button.on_click(self.go())
        self._change_settings.on_click(self.unlock())
        self.toggle.on_trait_change(set_color_for(self), str('value'))
        self._state_monitor.on_trait_change(self.state_change_handler(), str('value'))

    def display(self):
        """
        Display, and then format, this widget.

        Most IPython widget formatting must be done after the widget is
        created.
        """
        from IPython.display import display
        display(self)
        self.format()

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
        for child in self._go_container.children:
            child.set_css('padding', '5px')

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

    def state_change_handler(self):
        """
        Ties sanity state to go button controls and others
        """
        def change_handler():
            if self.is_sane is None:
                pass

            # Sorry about the double negative below, but the IPython widget
            # method is named DISabled...
            self._go_button.disabled = not self.is_sane

        return change_handler

    def go(self):
        def handler(b):
            """
            b is the button pressed
            """
            self.disabled = True
            # DO STUFF HERE!
            import time; time.sleep(1)
            # change button should really only appear after the work is done.
            self._change_settings.visible = True
            self._change_settings.disabled = False
            self._go_button.disabled = True
        return handler

    def unlock(self):
        def handler(b):
            self.disabled = False
            self._go_button.disabled = False
            self._change_settings.visible = False
        return handler


class CombinerWidget(ToggleGoWidget):
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
        self._clipping_widget.add_child(min_max)
        self._clipping_widget.add_child(sigma_clip)
        self._combine_method = \
            widgets.ToggleButtonsWidget(description="Combination method:",
                                        values=[
                                            'None',
                                            'Average',
                                            'Median'
                                        ])

        self.add_child(self._clipping_widget)
        self.add_child(self._combine_method)
        self.min_max = min_max
        self.sigma_clip = sigma_clip
        self._combine_method.on_trait_change(set_color_for(self), str('value'))

    @property
    def is_sane(self):
        """
        Indicates whether the combination of selected settings is at least
        remotely sane.
        """
        print("I am in sane")
        return self._combine_method.value != 'None'

    def format(self):
        super(CombinerWidget, self).format()
        self.min_max.format()
        self.sigma_clip.format()


class CosmicRaySettingsWidget(ToggleContainerWidget):
    def __init__(self, *args, **kwd):
        descript = kwd.pop('description', 'Clean cosmic rays?')
        kwd['description'] = descript
        super(CosmicRaySettingsWidget, self).__init__(*args, **kwd)
        cr_choices = widgets.DropdownWidget(
            description='Method:',
            values={'median': set_color_for, 'LACosmic': set_color_for}
        )
        self.container.children = [cr_choices]

    def display(self):
        from IPython.display import display
        display(self)


class SliceWidget(ToggleContainerWidget):
    def __init__(self, *arg, **kwd):
        super(SliceWidget, self).__init__(*arg, **kwd)
        drop_desc = ('Region is along all of')
        self._axis_selection = widgets.ContainerWidget()
        self._pre = widgets.ToggleButtonsWidget(description=drop_desc,
                                                values={"axis 0": 0,
                                                        "axis 1": 1})
        self._start = widgets.IntTextWidget(description='and on the other axis from index ')
        self._stop = widgets.IntTextWidget(description='up to (but not including):')
        self._axis_selection.children = [
            self._pre,
            self._start,
            self._stop
        ]
        self.add_child(self._axis_selection)
        #self.add_child(self._start)
        #self.add_child(self._stop)

    def format(self):
        super(SliceWidget, self).format()
        hbox_these = [self._axis_selection]  # [self, self.container]
        for hbox in hbox_these:
            hbox.remove_class('vbox')
            hbox.add_class('hbox')
        self._start.set_css('width', '30px')
        self._stop.set_css('width', '30px')


class OverscanWidget(SliceWidget):
    """docstring for OverscanWidget"""
    def __init__(self, *arg, **kwd):
        super(OverscanWidget, self).__init__(*arg, **kwd)
        poly_desc = "Fit polynomial to overscan?"
        self._polyfit = ToggleContainerWidget(description=poly_desc)
        poly_values = OrderedDict()
        poly_values["Order 0/one term (constant)"] = 1
        poly_values["Order 1/two term (linear)"] = 2
        poly_values["Order 2/three team (quadratic)"] = 3
        poly_values["Are you serious? Higher order is silly."] = None
        poly_dropdown = widgets.DropdownWidget(description="Choose fit",
                                               values=poly_values,
                                               value=1)
        self._polyfit.add_child(poly_dropdown)
        self.add_child(self._polyfit)

    def format(self):
        super(OverscanWidget, self).format()
        self._polyfit.format()
        self._polyfit.remove_class('vbox')
        self._polyfit.add_class('hbox')


class CalibrationStepWidget(ToggleContainerWidget):
    """
    Represents a calibration step that corresponds to a ccdproc command.

    Parameters
    ----------

    None
    """
    def __init__(self, *args, **kwd):
        super(CalibrationStepWidget, self).__init__(*args, **kwd)
        self._source_dict = {'Created in this notebook': 'notebook',
                             'File on disk': 'disk'}
        self._settings = \
            widgets.ContainerWidget(description="Reduction choices")

        self._source = widgets.ToggleButtonsWidget(description='Source:',
                                                   values=self._source_dict)
        self._file_select = widgets.DropdownWidget(description="Select file:",
                                                   values=["Not working yet"],
                                                   visible=False)
        self._settings.children = [self._source, self._file_select]
        self.add_child(self._settings)
        self._source.on_trait_change(self._file_select_visibility(),
                                     str('value_name'))

    def _file_select_visibility(self):
        def file_visibility(name, value):
            self._file_select.visible = self._source_dict[value] == 'disk'
        return file_visibility


class ReductionSettings(ToggleGoWidget):
    """docstring for ReductionSettings"""
    def __init__(self, *arg, **kwd):
        allow_flat = kwd.pop('allow_flat', True)
        allow_dark = kwd.pop('allow_dark', True)
        allow_bias = kwd.pop('allow_bias', True)
        super(ReductionSettings, self).__init__(*arg, **kwd)
        self._overscan = OverscanWidget(description='Subtract overscan?')
        self._trim = SliceWidget(description='Trim (specify region to keep)?')
        self._cosmic_ray = CosmicRaySettingsWidget()
        self._bias_calib = CalibrationStepWidget(description="Subtract bias?")
        self._dark_calib = CalibrationStepWidget(description="Subtract dark?")
        self._flat_calib = CalibrationStepWidget(description="Flat correct?")
        self.add_child(self._overscan)
        self.add_child(self._trim)
        self.add_child(self._cosmic_ray)

        if allow_bias:
            self.add_child(self._bias_calib)
        if allow_dark:
            self.add_child(self._dark_calib)
        if allow_flat:
            self.add_child(self._flat_calib)

    def display(self):
        from IPython.display import display
        display(self)
        self.format()


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
