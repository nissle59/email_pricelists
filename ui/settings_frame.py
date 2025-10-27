from typing import Self, TYPE_CHECKING

import ttkbootstrap as ttk
from ttkbootstrap.constants import *

if TYPE_CHECKING:
    from ui.gui import App


def create_settings_frame(self, notebook):
    tab_settings = ttk.Frame(notebook)
    notebook.add(tab_settings, text="⚙️ Настройки")

    lf = ttk.Labelframe(tab_settings, text="Настройки email", padding=10, bootstyle="primary")

    ttk.Label(lf, text="Тема интерфейса:", font=("Helvetica", 12)).grid(row=0, column=0, padx=10, pady=10,
                                                                                  sticky=W)

    self.theme_var = ttk.StringVar(value=self.style.theme.name)
    theme_box = ttk.Combobox(lf, textvariable=self.theme_var, values=self.style.theme_names())
    theme_box.grid(row=0, column=1, padx=10, pady=10)

    ttk.Button(
        lf,
        text="Применить",
        bootstyle="primary",
        command=self.change_theme
    ).grid(row=0, column=2, padx=10, pady=10)
    lf.pack()
