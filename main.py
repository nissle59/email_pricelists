import os

from ui.gui import App

if __name__ == "__main__":
    os.makedirs("attachments", exist_ok=True)
    app = App()
    app.mainloop()
