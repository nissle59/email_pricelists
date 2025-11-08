from tkinter import messagebox

import ttkbootstrap as ttk
from ttkbootstrap.constants import *
from crud import list_roles, add_role, update_role, delete_role, \
    get_role_by_name


class RolesEditor(ttk.Toplevel):
    def __init__(self, parent):
        super().__init__(parent)
        self.parent = parent
        self.title("Редактор ролей")
        self.geometry("600x400")
        self.resizable(True, True)

        # Переменные для хранения данных
        self.roles = []
        self.selected_role_id = None

        self.create_widgets()
        self.load_roles()
        self.center_window()

    def center_window(self):
        """Центрирование окна относительно родительского"""
        self.update_idletasks()
        width = self.winfo_width()
        height = self.winfo_height()
        x = (self.winfo_screenwidth() // 2) - (width // 2)
        y = (self.winfo_screenheight() // 2) - (height // 2)
        self.geometry(f'{width}x{height}+{x}+{y}')

    def create_widgets(self):
        """Создание элементов интерфейса"""
        # Основной фрейм
        main_frame = ttk.Frame(self, padding="10")
        main_frame.grid(row=0, column=0, sticky=(W, E, N, S))

        # Конфигурация весов строк и столбцов
        self.columnconfigure(0, weight=1)
        self.rowconfigure(0, weight=1)
        main_frame.columnconfigure(1, weight=1)
        main_frame.rowconfigure(1, weight=1)

        # Фрейм формы
        form_frame = ttk.LabelFrame(main_frame, text="Данные роли", padding="5")
        form_frame.grid(row=0, column=0, columnspan=2, sticky=(W, E), pady=(0, 10))
        form_frame.columnconfigure(1, weight=1)

        # Поле названия роли
        ttk.Label(form_frame, text="Название:").grid(row=0, column=0, sticky=W, padx=(0, 5))
        self.name_var = ttk.StringVar()
        self.name_entry = ttk.Entry(form_frame, textvariable=self.name_var, width=30)
        self.name_entry.grid(row=0, column=1, sticky=(W, E), padx=(0, 10))

        # Checkbox для обязательной роли
        self.required_var = ttk.BooleanVar()
        self.required_check = ttk.Checkbutton(form_frame, text="Обязательная роль",
                                              variable=self.required_var)
        self.required_check.grid(row=1, column=0, columnspan=2, sticky=W, pady=(5, 0))

        # Кнопки управления
        buttons_frame = ttk.Frame(form_frame)
        buttons_frame.grid(row=2, column=0, columnspan=2, sticky=(W, E), pady=(10, 0))

        self.add_btn = ttk.Button(buttons_frame, text="Добавить", command=self.add_role)
        self.add_btn.grid(row=0, column=0, padx=(0, 5))

        self.update_btn = ttk.Button(buttons_frame, text="Обновить", command=self.update_role, state="disabled")
        self.update_btn.grid(row=0, column=1, padx=(0, 5))

        self.delete_btn = ttk.Button(buttons_frame, text="Удалить", command=self.delete_role, state="disabled")
        self.delete_btn.grid(row=0, column=2, padx=(0, 5))

        self.clear_btn = ttk.Button(buttons_frame, text="Очистить", command=self.clear_form)
        self.clear_btn.grid(row=0, column=3)

        # Таблица ролей
        list_frame = ttk.LabelFrame(main_frame, text="Список ролей", padding="5")
        list_frame.grid(row=1, column=0, columnspan=2, sticky=(W, E, N, S))
        list_frame.columnconfigure(0, weight=1)
        list_frame.rowconfigure(0, weight=1)

        # Создание Treeview
        columns = ("id", "name", "required")
        self.tree = ttk.Treeview(list_frame, columns=columns, show="headings", height=15)

        # Настройка колонок
        self.tree.heading("id", text="ID")
        self.tree.heading("name", text="Название")
        self.tree.heading("required", text="Обязательная")

        self.tree.column("id", width=50, anchor=CENTER)
        self.tree.column("name", width=200)
        self.tree.column("required", width=100, anchor=CENTER)

        # Scrollbar для таблицы
        scrollbar = ttk.Scrollbar(list_frame, orient=VERTICAL, command=self.tree.yview)
        self.tree.configure(yscrollcommand=scrollbar.set)

        # Размещение элементов
        self.tree.grid(row=0, column=0, sticky=(W, E, N, S))
        scrollbar.grid(row=0, column=1, sticky=(N, S))

        # Привязка события выбора
        self.tree.bind("<<TreeviewSelect>>", self.on_role_select)

        # Кнопка закрытия
        ttk.Button(main_frame, text="Закрыть", command=self.destroy).grid(
            row=2, column=1, sticky=E, pady=(10, 0))

    def load_roles(self):
        """Загрузка списка ролей из базы данных"""
        try:
            self.roles = list_roles()
            self.update_treeview()
        except Exception as e:
            messagebox.showerror("Ошибка", f"Не удалось загрузить роли: {str(e)}")

    def update_treeview(self):
        """Обновление отображения таблицы ролей"""
        # Очистка текущих данных
        for item in self.tree.get_children():
            self.tree.delete(item)

        # Заполнение новыми данными
        for role in self.roles:
            required_text = "Да" if role.required else "Нет"
            self.tree.insert("", END, values=(role.id, role.name, required_text))

    def on_role_select(self, event):
        """Обработка выбора роли в таблице"""
        selection = self.tree.selection()
        if not selection:
            return

        item = selection[0]
        values = self.tree.item(item, "values")

        if values:
            self.selected_role_id = int(values[0])
            role = next((r for r in self.roles if r.id == self.selected_role_id), None)

            if role:
                self.name_var.set(role.name)
                self.required_var.set(role.required)

                # Активация кнопок редактирования и удаления
                self.update_btn.config(state="normal")
                self.delete_btn.config(state="normal")
                self.add_btn.config(state="disabled")

    def clear_form(self):
        """Очистка формы и сброс выбора"""
        self.name_var.set("")
        self.required_var.set(False)
        self.selected_role_id = None
        self.tree.selection_remove(self.tree.selection())

        # Сброс состояния кнопок
        self.update_btn.config(state="disabled")
        self.delete_btn.config(state="disabled")
        self.add_btn.config(state="normal")

    def validate_form(self):
        """Проверка валидности данных формы"""
        name = self.name_var.get().strip()
        if not name:
            messagebox.showwarning("Внимание", "Введите название роли")
            self.name_entry.focus()
            return False
        return True

    def add_role(self):
        """Добавление новой роли"""
        if not self.validate_form():
            return

        name = self.name_var.get().strip()
        required = self.required_var.get()

        try:
            # Проверка на существование роли с таким именем
            existing_role = get_role_by_name(name)
            if existing_role:
                messagebox.showwarning("Внимание", f"Роль с именем '{name}' уже существует")
                return

            # Добавление роли
            new_role = add_role(name, required)
            if new_role:
                messagebox.showinfo("Успех", f"Роль '{name}' успешно добавлена")
                self.load_roles()
                self.clear_form()
            else:
                messagebox.showerror("Ошибка", "Не удалось добавить роль")

        except Exception as e:
            messagebox.showerror("Ошибка", f"Не удалось добавить роль: {str(e)}")

    def update_role(self):
        """Обновление выбранной роли"""
        if not self.selected_role_id or not self.validate_form():
            return

        name = self.name_var.get().strip()
        required = self.required_var.get()

        try:
            # Проверка на существование другой роли с таким именем
            existing_role = get_role_by_name(name)
            if existing_role and existing_role.id != self.selected_role_id:
                messagebox.showwarning("Внимание", f"Роль с именем '{name}' уже существует")
                return

            # Обновление роли
            updated_role = update_role(self.selected_role_id, name, required)
            if updated_role:
                messagebox.showinfo("Успех", f"Роль успешно обновлена")
                self.load_roles()
                self.clear_form()
            else:
                messagebox.showerror("Ошибка", "Не удалось обновить роль")

        except Exception as e:
            messagebox.showerror("Ошибка", f"Не удалось обновить роль: {str(e)}")

    def delete_role(self):
        """Удаление выбранной роли"""
        if not self.selected_role_id:
            return

        role_name = self.name_var.get()
        result = messagebox.askyesno(
            "Подтверждение удаления",
            f"Вы уверены, что хотите удалить роль '{role_name}'?"
        )

        if not result:
            return

        try:
            deleted_role = delete_role(self.selected_role_id)
            if deleted_role:
                messagebox.showinfo("Успех", f"Роль '{role_name}' успешно удалена")
                self.load_roles()
                self.clear_form()
            else:
                messagebox.showerror("Ошибка", "Не удалось удалить роль")

        except Exception as e:
            messagebox.showerror("Ошибка", f"Не удалось удалить роль: {str(e)}")