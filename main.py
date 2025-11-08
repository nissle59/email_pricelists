from utils.paths import pm
import os
#os.makedirs(pm.get_executable_dir_path("attachments"), exist_ok=True)
from ui.gui import App

if __name__ == "__main__":

    app = App()
    app.mainloop()
