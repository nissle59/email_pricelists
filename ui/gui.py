import ttkbootstrap as ttk
from ttkbootstrap.constants import *

from ui.about_frame import create_about_frame
from ui.main_frame import create_main_frame
from ui.settings_frame import create_settings_frame


class App(ttk.Window):
    def __init__(self):
        super().__init__(
            title="Моё приложение",
            themename="flatly",  # попробуй также: superhero, darkly, cyborg, morph, vapor
            size=(700, 500),
            resizable=(True, True)
        )

        self.create_tabs()

    def create_tabs(self):
        notebook = ttk.Notebook(self, bootstyle="info")
        notebook.pack(fill=BOTH, expand=YES, padx=10, pady=10)

        create_main_frame(self, notebook)
        create_settings_frame(self, notebook)
        create_about_frame(self, notebook)

    def change_theme(self):
        new_theme = self.theme_var.get()
        self.style.theme_use(new_theme)
