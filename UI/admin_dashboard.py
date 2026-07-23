

import tkinter as tk
from tkinter import ttk, messagebox

import styles
import mock_data

STATUS_OPTIONS = ["Pending", "Reviewed", "Escalated"]


class AdminDashboard(ttk.Frame):
    def __init__(self, parent, controller):
        super().__init__(parent, style="App.TFrame")
        self.controller = controller

        self._build_topbar()

        self.body = ttk.Frame(self, style="App.TFrame", padding=20)
        self.body.pack(fill="both", expand=True)

        self._render_conflicts()

   # topbar
    def _build_topbar(self):
        bar = ttk.Frame(self, style="Card.TFrame", padding=(20, 10))
        bar.pack(fill="x")

        left = ttk.Frame(bar, style="Card.TFrame")
        left.pack(side="left")
        ttk.Label(left, text="Admin dashboard", style="CardTitle.TLabel").pack(anchor="w")
        ttk.Label(left, text="Supervisor", style="Muted.TLabel").pack(anchor="w")

        ttk.Button(bar, text="Log out", style="Secondary.TButton",
                   command=lambda: self.controller.show_screen("login")).pack(side="right")

    def _render_conflicts(self):
        for widget in self.body.winfo_children():
            widget.destroy()

        card = ttk.Frame(self.body, style="Card.TFrame", padding=16)
        card.pack(fill="both", expand=True)

        ttk.Label(card, text="Conflicting hazard reviews",
                  style="CardTitle.TLabel").pack(anchor="w")
        ttk.Label(card, text="Two field agents disagreed on a hazard's status. Pick the final status for each.",
                  style="Muted.TLabel").pack(anchor="w", pady=(0, 12))

        #TODO!
        # this is currently standing in for demonstartion, i need to figure out how to implement a real query to get conflicts
        unresolved = [c for c in mock_data.CONFLICTS if not c["resolved"]]

        if not unresolved:
            ttk.Label(card, text="No conflicts to resolve right now.",
                      style="Muted.TLabel").pack(anchor="w", pady=8)
            return

        for conflict in unresolved:
            self._build_conflict_row(card, conflict)

    def _build_conflict_row(self, parent, conflict):
        row = ttk.Frame(parent, style="Card.TFrame", padding=(0, 10))
        row.pack(fill="x")

        # clean up conflict list a bit
        ttk.Separator(row).pack(fill="x", pady=(0, 10))

        header = ttk.Frame(row, style="Card.TFrame")
        header.pack(fill="x")
        ttk.Label(header, text=conflict["hazard_id"], style="CardTitle.TLabel").pack(side="left")

        detail_text = (
            f"{conflict['agent_a']} marked \u2018{conflict['status_a']}\u2019 \u00b7 "
            f"{conflict['agent_b']} marked \u2018{conflict['status_b']}\u2019"
        )
        ttk.Label(row, text=detail_text, style="Muted.TLabel").pack(anchor="w", pady=(2, 8))

        action_row = ttk.Frame(row, style="Card.TFrame")
        action_row.pack(fill="x")

        ttk.Label(action_row, text="Final status:", style="Muted.TLabel").pack(side="left", padx=(0, 6))
        # TODO!
        # default is going to be the second agents update. need to ask Sara about procedure regarding how they want it defaulted

        status_var = tk.StringVar(value=conflict["status_b"])
        status_combo = ttk.Combobox(
            action_row, textvariable=status_var, state="readonly",
            values=STATUS_OPTIONS, width=14,
        )
        status_combo.pack(side="left", padx=(0, 10))

        ttk.Button(
            action_row, text="Resolve", style="Primary.TButton",
            command=lambda hid=conflict["hazard_id"], var=status_var: self._resolve(hid, var.get()),
        ).pack(side="left")

    def _resolve(self, hazard_id, final_status):
        # TODO!
        # THis will need a real update method once i figure out how to manage updates and stuff

        mock_data.resolve_conflict(hazard_id, final_status)
        messagebox.showinfo("Resolved", f"{hazard_id} set to '{final_status}'.")
        self._render_conflicts()
