import ttkbootstrap as ttk
from ttkbootstrap.constants import *

from crud import get_settings
from ui.about_frame import create_about_frame
from ui.main_frame import MainFrame
from ui.settings_frame import create_settings_frame
from ya_client import YandexIMAPClient


class App(ttk.Window):
    def __init__(self):
        super().__init__(
            title="Агрегатор прайс-листов",
            themename="flatly",  # попробуй также: superhero, darkly, cyborg, morph, vapor
            size=(1280, 800),
            resizable=(True, True)
        )
        s = get_settings()
        #print(s)
        self.email_client = YandexIMAPClient(s.get('email_username'), s.get('email_password'))
        self.create_tabs()

    def create_tabs(self):
        notebook = ttk.Notebook(self, bootstyle="info")
        notebook.pack(fill=BOTH, expand=YES, padx=10, pady=10)

        MainFrame(notebook)
        #create_main_frame(self, notebook)
        create_settings_frame(self, notebook)
        #create_about_frame(self, notebook)

    def change_theme(self):
        new_theme = self.theme_var.get()
        self.style.theme_use(new_theme)
