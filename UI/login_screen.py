

import tkinter as tk
from tkinter import ttk

import styles
import auth


class LoginScreen(ttk.Frame):

    def __init__(self, parent, controller):
        super().__init__(parent, style="App.TFrame")
        self.controller = controller

        # Center card in the middle of window.
        self.grid_rowconfigure(0, weight=1)
        self.grid_columnconfigure(0, weight=1)

        card = ttk.Frame(self, style="Card.TFrame", padding=28)
        card.grid(row=0, column=0)

        ttk.Label(card, text="Hazardous tree mapping",
                  style="CardTitle.TLabel").pack(anchor="w")
        ttk.Label(card, text="Sign in to your account",
                  style="Muted.TLabel").pack(anchor="w", pady=(0, 16))

        # Error message
        self.error_var = tk.StringVar(value="")
        self.error_label = ttk.Label(
            card, textvariable=self.error_var,
            style="Muted.TLabel", foreground=styles.DANGER, wraplength=280,
        )
        self.error_label.pack(anchor="w", pady=(0, 4))

        #  Email 
        ttk.Label(card, text="Email", style="Muted.TLabel").pack(anchor="w")
        self.email_var = tk.StringVar()
        ttk.Entry(card, textvariable=self.email_var, width=32).pack(
            fill="x", pady=(2, 10)
        )

        # Password 
        ttk.Label(card, text="Password", style="Muted.TLabel").pack(anchor="w")
        self.password_var = tk.StringVar()
        ttk.Entry(card, textvariable=self.password_var, show="*", width=32).pack(
            fill="x", pady=(2, 10)
        )

        ttk.Button(
            card, text="Log in", style="Primary.TButton",
            command=self._attempt_login,
        ).pack(fill="x", pady=(6, 0))

        ttk.Label(
            card, text="Forgot your password?", style="Muted.TLabel",
            cursor="hand2",
        ).pack(pady=(12, 0))

    def _attempt_login(self):
        email = self.email_var.get()
        password = self.password_var.get()

        if not email.strip() or not password.strip():
            self.error_var.set("Enter an email and password to continue.")
            return

        # looks the email/password up in users.csv and returns the matching role ("pilot" or "agent"), or None
        role = auth.authenticate(email, password)
        if role is None:
            self.error_var.set("Incorrect email or password.")
            return

        self.error_var.set("")

        # role must be "pilot" or "agent" to match screen names
        self.controller.show_screen(role)

    def reset(self):
        self.email_var.set("")
        self.password_var.set("")
        self.error_var.set("")
