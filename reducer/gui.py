from __future__ import (division, print_function, absolute_import,
                        unicode_literals)

from IPython.html import widgets
import matplotlib.pyplot as plt

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
