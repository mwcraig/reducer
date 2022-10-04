import ipywidgets as ipw
from traitlets import Unicode

all = ['ButtonHolder']


class ButtonHolder(ipw.VBox):
    selected_button = Unicode(help='Button that was most recently clicked')\
                      .tag(sync=True)

    def __init__(self, descriptions=None, **kwd):
        super().__init__(**kwd)
        self._buttons = {}
        self.button_layout = ipw.Layout(width='100%',
                                        height='25px',
                                        min_height='25px',
                                        align_content='flex-start',
                                        justify_content='flex-start')
        font_settings = dict(
            font_weight='bold',
            font_size='0.7em'
        )
        self.unselected_button_style = ipw.ButtonStyle(**font_settings)
        self.selected_button_style = ipw.ButtonStyle(
            button_color='CadetBlue',
            **font_settings
        )

        if descriptions is not None:
            self.set_buttons(descriptions)

        self.layout = ipw.Layout(overflow='hidden scroll')

    def set_buttons(self, descriptions):
        buttons = {}
        for desc in descriptions:
            b = ipw.Button(description=desc,
                           layout=self.button_layout,
                           style=self.unselected_button_style
                          )
            b.on_click(self._make_button_handler())
            buttons[desc] = b
        self._buttons = buttons
        self.children = list(buttons.values())

    def _make_button_handler(self):
        def button_handler(button):
            if (self.selected_button and
                    (button.description != self.selected_button)):

                self._buttons[self.selected_button].style = self.unselected_button_style

            self.selected_button = button.description
            button.style = self.selected_button_style

        return button_handler
