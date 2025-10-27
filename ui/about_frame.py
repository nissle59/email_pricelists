import ttkbootstrap as ttk


def create_about_frame(self, notebook):
    tab_about = ttk.Frame(notebook)
    notebook.add(tab_about, text="ℹ️ О программе")

    ttk.Label(
        tab_about,
        text="Приложение на Tkinter с использованием ttkbootstrap.\n\nАвтор: Никита\nВерсия: 1.0.0",
        font=("Helvetica", 12),
        justify="center"
    ).pack(expand=True)
