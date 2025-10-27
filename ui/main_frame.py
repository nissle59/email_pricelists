import ttkbootstrap as ttk
from ttkbootstrap.constants import *


def create_main_frame(self, notebook):
    tab_main = ttk.Frame(notebook)
    notebook.add(tab_main, text="🏠 Главная")

    ttk.Label(
        tab_main,
        text="Добро пожаловать!",
        font=("Helvetica", 18, "bold")
    ).pack(pady=40)

    ttk.Button(
        tab_main,
        text="Нажми меня",
        bootstyle="success-outline",
        command=lambda: ttk.toast.ToastNotification(
            title="Ура!",
            message="Кнопка нажата 🎉",
            duration=2000
        ).show_toast()
    ).pack(pady=10)
