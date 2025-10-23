import ttkbootstrap as ttk
from ttkbootstrap.constants import *

class App(ttk.Window):
    def __init__(self):
        super().__init__(
            title="Моё красивое приложение",
            themename="superhero",  # попробуй: flatly, minty, darkly, cyborg, vapor и др.
            size=(600, 400),
            resizable=(False, False)
        )

        self.create_widgets()

    def create_widgets(self):
        # Заголовок
        title = ttk.Label(
            self,
            text="Добро пожаловать!",
            font=("Helvetica", 20, "bold"),
        )
        title.pack(pady=30)

        # Ввод текста
        frame = ttk.Frame(self)
        frame.pack(pady=20)

        ttk.Label(frame, text="Введите имя:", font=("Helvetica", 12)).grid(row=0, column=0, padx=5, pady=5)
        self.name_var = ttk.StringVar()
        name_entry = ttk.Entry(frame, textvariable=self.name_var, width=30)
        name_entry.grid(row=0, column=1, padx=5, pady=5)
        name_entry.focus()

        # Кнопка
        button = ttk.Button(
            self,
            text="Поприветствовать",
            bootstyle="success-outline",
            command=self.say_hello
        )
        button.pack(pady=20)

        # Вывод результата
        self.output_label = ttk.Label(self, text="", font=("Helvetica", 14))
        self.output_label.pack(pady=10)

    def say_hello(self):
        name = self.name_var.get().strip()
        if name:
            self.output_label.config(text=f"Привет, {name}! 👋")
        else:
            self.output_label.config(text="Введите имя, пожалуйста!")

if __name__ == "__main__":
    app = App()
    app.mainloop()