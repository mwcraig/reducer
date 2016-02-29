from __future__ import (division, print_function, absolute_import,
                        unicode_literals)

from .ipython_version_helper import ipython_version_as_string

if ipython_version_as_string().startswith('3'):
    from IPython.html import widgets
    from IPython.utils.traitlets import link
else:
    import ipywidgets as widgets
    from traitlets import link

__all__ = [
    'ToggleContainer',
    'ToggleMinMax',
    'ToggleGo',
    'set_color_for',
]


class ToggleContainer(widgets.FlexBox):
    """
    A widget whose state controls the visibility of its chilren.

    Parameters
    ----------

    Same as parameters for a `~IPython.html.widgets.Box`, but
    note that the description of the ToggleContainer is used to set the
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

    Do *NOT* set the children of the ToggleContainer; set the children
    of ``ToggleContainer.children`` or use the `add_child` method.
    """
    def __init__(self, *args, **kwd):
        toggle_types = {'checkbox': widgets.Checkbox,
                        'button': widgets.ToggleButton}
        toggle_type = kwd.pop('toggle_type', 'checkbox')
        if toggle_type not in toggle_types:
            raise ValueError('toggle_type must be one of '
                             '{}'.format(toggle_type.keys()))
        super(ToggleContainer, self).__init__(*args, **kwd)
        self._toggle_container = widgets.Box(description='toggle holder')
        self._checkbox = toggle_types[toggle_type](description=self.description)
        self._toggle_container.children = [self._checkbox]
        self._container = widgets.Box(description="Toggle-able container")
        self._state_monitor = widgets.Checkbox(visible=False)

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
        # self._toggle_container.set_css('padding', '3px')
        self._toggle_container.padding = '3px'

        # self.container.set_css('padding', '0px 0px 0px 30px')
        self.container.padding = '0px 0px 0px 30px'

        #self.container.set_css('border', '1px red solid')
        #self._toggle_container.set_css('border', '1px red solid')

        # self._toggle_container.remove_class('start')
        # self._toggle_container.add_class('center')
        self._toggle_container.align = 'center'

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

        if isinstance(child, ToggleContainer):
            # If the child is a ToggleContainer we only need to link in
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


class ToggleMinMax(ToggleContainer):
    """
    Widget for setting a minimum and maximum integer value, controlled by
    a toggle.

    Parameters
    ----------

    description : str
        Text to be displayed in the toggle.
    """
    def __init__(self, *args, **kwd):
        super(ToggleMinMax, self).__init__(*args, **kwd)
        self._min_box = widgets.FloatText(description="Low threshold")
        self._max_box = widgets.FloatText(description="High threshold")
        self.add_child(self._min_box)
        self.add_child(self._max_box)

    def format(self):
        super(ToggleMinMax, self).format()
        hbox_these = [self, self.container]
        for hbox in hbox_these:
            hbox.orientation = 'horizontal'
        for child in self.container.children:
            # child.set_css('width', '30px')
            child.width = '30px'

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

class ToggleGo(ToggleContainer):
    """
    ToggleContainer whose state is linked to a button.

    The intent is for that button to be activated when the contents
    of the container are in a "sane" state.
    """
    def __init__(self, *args, **kwd):
        super(ToggleGo, self).__init__(*args, **kwd)
        self._go_container = widgets.HBox(visible=self.toggle.value)
        self._go_button = widgets.Button(description="Lock settings and Go!",
                                         disabled=True, visible=False)
        self._change_settings = widgets.Button(description="Unlock settings",
                                               disabled=True,
                                               visible=False)
        self._go_container.children = [self._go_button, self._change_settings]
        self._progress_container = widgets.Box()
        self._progress_bar = widgets.FloatProgress(min=0, max=1.0,
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
        super(ToggleGo, self).format()
        for child in self.container.children:
            try:
                child.format()
            except AttributeError:
                pass
        # self._clipping_widget.format()

        # self.container.set_css({'border': '1px grey solid',
        #                        'border-radius': '10px'})
        self.container.border_width = '1px'
        self.container.border_color = 'gray'
        self.container.border_radius = '10px'

        # self.container.set_css('width', '100%')
        self.container.width = '100%'

        # self.container.set_css('padding', '5px')
        self.container.padding = '5px'

        # self._toggle_container.set_css('width', '100%')
        self._toggle_container.width = '100%'

        # self._checkbox.set_css('width', '100%')
        self._checkbox.width = '100%'

        # self._go_container.set_css('padding', '5px')
        self._go_container.padding = '5px'

        # self._go_container.set_css('width', '100%')
        self._go_container.width = '100%'

        # self._go_button.add_class('box-flex1')
        self._go_button.width = '100%'
        # self._change_settings.add_class('box-flex3')
        self._change_settings.width = '30%'

        #self._go_button.add_class('btn-info')
        self._go_button.button_style = 'info'

        # self._change_settings.add_class('btn-inverse')
        # btn-inverse has been removed from Bootstrap 3.
        self._change_settings.button_style = 'primary'

        # self._progress_container.set_css('width', '100%')
        self._progress_bar.width = '100%'

        #self._progress_bar.add_class('progress-info')
        self._progress_bar.bar_style = 'info'

        #self._progress_bar.set_css('width', '90%')
        for child in self._go_container.children:
            # child.set_css('margin', '5px')
            child.margin = '5px'

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
            self._go_button.width = '68%'
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
            self._go_button.width = '100%'
        return handler

    def action(self):
        """
        The default action is to invoke the action of each child with an
        update of the progress bar along the way.
        """
        self.progress_bar.visible = True
        self.progress_bar.value = 0
        for idx, child in enumerate(self.container.children):
            self.progress_bar.value = (idx + 1) / (len(self.children) + 1)

            try:
                child.action()
            except AttributeError:
                pass
            self.progress_bar.value = (idx + 1)/len(self.children)
            # Sleep for a bit so we can see progress happening.

        self.progress_bar.visible = False


def set_color_for(a_widget):
    def set_color(name, value):
        if a_widget.toggle.value:
            if not a_widget.is_sane:
                a_widget.toggle.button_style = 'warning'
            else:
                a_widget.toggle.button_style = 'success'
        else:
            a_widget.toggle.button_style = None
    return set_color
