
import tkinter as tk
from tkinter import ttk

import styles
from login_screen import LoginScreen
from pilot_dashboard import PilotDashboard
from field_agent_screen import FieldAgentScreen
from admin_dashboard import AdminDashboard


class App(tk.Tk):

    def __init__(self):
        super().__init__()
        self.title("Hazardous Tree Mapping System")
        self.geometry("1100x720")
        self.minsize(900, 600)

        styles.apply_theme(self)

        container = ttk.Frame(self, style="App.TFrame")
        container.pack(fill="both", expand=True)
        container.grid_rowconfigure(0, weight=1)
        container.grid_columnconfigure(0, weight=1)

        self.screens = {}
        self._build_screens(container)

        self.show_screen("login")

    def _build_screens(self, container):
        for name, ScreenClass in (
            ("login", LoginScreen),
            ("pilot", PilotDashboard),
            ("agent", FieldAgentScreen),
            ("admin", AdminDashboard),
        ):
            screen = ScreenClass(container, self)
            screen.grid(row=0, column=0, sticky="nsew")
            self.screens[name] = screen

    def show_screen(self, name: str):
        if name == "login" and "login" in self.screens:
            self.screens["login"].reset()
        self.screens[name].tkraise()


if __name__ == "__main__":
    app = App()
    app.mainloop()