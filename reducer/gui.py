from __future__ import (division, print_function, absolute_import,
                        unicode_literals)
from collections import OrderedDict
import os

from IPython.html import widgets
import matplotlib.pyplot as plt
import msumastro


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
            print("Parents are:", parents)
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
        self._top.set_css({'width': '50%'})
        for name, obj in self._gui_objects.iteritems():
            if isinstance(obj, widgets.AccordionWidget):
                for idx, child in enumerate(obj.children):
                    if not isinstance(child, widgets.SelectWidget):
                        obj.set_title(idx, child.description)
            #obj.set_css({'width': '100%',})
            #obj.add_class('well')
