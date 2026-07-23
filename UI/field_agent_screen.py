

import tkinter as tk
from tkinter import ttk, messagebox
from datetime import date

import styles
import mock_data

SEVERITY_COLORS = {
    "high": styles.DANGER,
    "medium": styles.WARNING,
    "low": styles.SUCCESS,
}


class FieldAgentScreen(ttk.Frame):
    def __init__(self, parent, controller):
        super().__init__(parent, style="App.TFrame")
        self.controller = controller
        self.selected_hazard_id = None
        self.selected_image_type = "drone"

        self._build_topbar()

        body = ttk.Frame(self, style="App.TFrame", padding=20)
        body.pack(fill="both", expand=True)

        self._build_filters(body)

        review_body = ttk.Frame(body, style="App.TFrame")
        review_body.pack(fill="both", expand=True)

        self._build_map_panel(review_body)
        self._build_detail_panel(review_body)

        self._build_ai_summary_card(body)

        self._refresh_map_and_list()

   
    def _build_topbar(self):
        bar = ttk.Frame(self, style="Card.TFrame", padding=(20, 10))
        bar.pack(fill="x")

        left = ttk.Frame(bar, style="Card.TFrame")
        left.pack(side="left")
        ttk.Label(left, text="Hazard review — Kananaskis block 4",
                  style="CardTitle.TLabel").pack(anchor="w")
        ttk.Label(left, text="Field agent", style="Muted.TLabel").pack(anchor="w")

        right = ttk.Frame(bar, style="Card.TFrame")
        right.pack(side="right")
        ttk.Button(right, text="Generate PDF report", style="Secondary.TButton",
                   command=self._generate_report).pack(side="left", padx=(0, 10))
        ttk.Button(right, text="Log out", style="Secondary.TButton",
                   command=lambda: self.controller.show_screen("login")).pack(side="left")

        # TODO!
        #will need to use real conflicts but i'll need to use data to figure that out
        unresolved = [c for c in mock_data.CONFLICTS if not c["resolved"]]
        if unresolved:
            badge = tk.Label(
                bar, text=f"{len(unresolved)} conflicting review",
                bg=styles.WARNING_BG, fg=styles.WARNING, font=styles.FONT_LABEL,
                padx=10, pady=3, cursor="hand2",
            )
            badge.pack(side="right", padx=(0, 10))
            badge.bind("<Button-1>", lambda e: self._show_conflict())

    def _build_filters(self, parent):
        row = ttk.Frame(parent, style="App.TFrame")
        row.pack(fill="x", pady=(0, 12))

        # TODO!
        #filters date but will need to be updated to use real data once i have access
        self.date_filter_var = tk.StringVar(value="All dates")
        date_combo = ttk.Combobox(
            row, textvariable=self.date_filter_var, state="readonly",
            values=["All dates", "Last 7 days", "Last 30 days"], width=16,
        )
        date_combo.pack(side="left", padx=(0, 10))
        date_combo.bind("<<ComboboxSelected>>", lambda e: self._refresh_map_and_list())

        # TODO! 
        # will filter against severity once data implemebnted and i update it
        self.severity_filter_var = tk.StringVar(value="All severities")
        severity_combo = ttk.Combobox(
            row, textvariable=self.severity_filter_var, state="readonly",
            values=["All severities", "high", "medium", "low"], width=16,
        )
        severity_combo.pack(side="left")
        severity_combo.bind("<<ComboboxSelected>>", lambda e: self._refresh_map_and_list())

    def _build_map_panel(self, parent):
        # TODO!
        # placeholder for interactive map, i need to figure out how to implement it
        map_frame = ttk.Frame(parent, style="Card.TFrame", padding=8)
        map_frame.pack(side="left", fill="both", expand=True, padx=(0, 8))

        self.map_canvas = tk.Canvas(map_frame, bg=styles.BG, height=320,
                                     highlightthickness=1,
                                     highlightbackground=styles.BORDER)
        self.map_canvas.pack(fill="both", expand=True)



    def _build_detail_panel(self, parent):
        self.detail_frame = ttk.Frame(parent, style="Card.TFrame", padding=14, width=260)
        self.detail_frame.pack(side="left", fill="y")
        self.detail_frame.pack_propagate(False)

        # requires AI training to implement properly
    def _build_ai_summary_card(self, parent):
        card = ttk.Frame(parent, style="Card.TFrame", padding=16)
        card.pack(fill="x", pady=(16, 0))

        ttk.Label(card, text="AI hazard summary", style="CardTitle.TLabel").pack(anchor="w")
        ttk.Label(card, text="Generated from drone and satellite imagery for the selected tree.",
                  style="Muted.TLabel").pack(anchor="w", pady=(0, 8))

        # TODO!
        # mock summary, this will be updated to use the real AI summary
        self.ai_summary_var = tk.StringVar(
            value="Select a hazard on the map to view its AI-generated summary."
        )
        ttk.Label(card, textvariable=self.ai_summary_var, style="Card.TLabel",
                  wraplength=800, justify="left").pack(anchor="w")

    def _filtered_hazards(self):
        # TODO! 
        # #this whole method should eventually become a real filtered query (DB query, API call instead of filtering the mock_data.HAZARDS list in memory.
        date_choice = self.date_filter_var.get()
        severity_choice = self.severity_filter_var.get()

        results = []
        for h in mock_data.HAZARDS:
            days_ago = (date.today() - h["flagged_date"]).days

            if date_choice == "Last 7 days" and days_ago > 7:
                continue
            if date_choice == "Last 30 days" and days_ago > 30:
                continue
            if severity_choice != "All severities" and h["severity"] != severity_choice:
                continue
            results.append(h)
        return results

    def _refresh_map_and_list(self):
        hazards = self._filtered_hazards()

        self.map_canvas.delete("pin")
        for h in hazards:
            color = SEVERITY_COLORS[h["severity"]]
            item = self.map_canvas.create_oval(
                h["x"] - 6, h["y"] - 6, h["x"] + 6, h["y"] + 6,
                fill=color, outline="", tags=("pin", h["id"]),
            )
            self.map_canvas.tag_bind(item, "<Button-1>",
                                      lambda e, hid=h["id"]: self._select_hazard(hid))

        # Keep the current selection if it's still visible, otherwise  back to the first visible hazard
        visible_ids = [h["id"] for h in hazards]
        if self.selected_hazard_id not in visible_ids:
            self.selected_hazard_id = visible_ids[0] if visible_ids else None

        self._render_detail()

    def _select_hazard(self, hazard_id):
        self.selected_hazard_id = hazard_id
        self.selected_image_type = "drone"
        self._render_detail()

    def _get_selected_hazard(self):
        return next((h for h in mock_data.HAZARDS if h["id"] == self.selected_hazard_id), None)

    def _render_detail(self):
        for widget in self.detail_frame.winfo_children():
            widget.destroy()

        hazard = self._get_selected_hazard()
        if not hazard:
            ttk.Label(self.detail_frame, text="No hazard matches the current filters.",
                      style="Muted.TLabel", wraplength=230).pack(anchor="w")
            self.ai_summary_var.set("Select a hazard on the map to view its AI-generated summary.")
            return

        header = ttk.Frame(self.detail_frame, style="Card.TFrame")
        header.pack(anchor="w", fill="x")
        ttk.Label(header, text=hazard["id"], style="CardTitle.TLabel").pack(side="left")
        tk.Label(header, text=hazard["severity"], bg=SEVERITY_COLORS[hazard["severity"]],
                 fg="white", font=styles.FONT_LABEL, padx=8, pady=1).pack(side="left", padx=(6, 0))

        ttk.Label(self.detail_frame, text=hazard["description"], style="Muted.TLabel",
                  wraplength=230).pack(anchor="w", pady=(2, 12))

        #  Image toggle
        # TODO!

        #will need to update to real image paths
        toggle_row = ttk.Frame(self.detail_frame, style="Card.TFrame")
        toggle_row.pack(fill="x", pady=(0, 8))
        drone_btn = ttk.Button(toggle_row, text="Drone image", style="Secondary.TButton",
                                command=lambda: self._set_image_type("drone"))
        drone_btn.pack(side="left", fill="x", expand=True, padx=(0, 4))
        sat_btn = ttk.Button(toggle_row, text="Satellite image", style="Secondary.TButton",
                              command=lambda: self._set_image_type("satellite"))
        sat_btn.pack(side="left", fill="x", expand=True)

        image_path = hazard["drone_image_path"] if self.selected_image_type == "drone" else hazard["satellite_image_path"]
        placeholder_text = image_path or f"{self.selected_image_type.title()} image placeholder"
        img_box = tk.Label(self.detail_frame, text=placeholder_text, bg="#e7e9e4",
                            fg=styles.TEXT_MUTED, font=styles.FONT_LABEL, height=6)
        img_box.pack(fill="x", pady=(0, 12))

        #  Review status
        # TODO! on change, this should PATCH/update the real hazard record's status, and should trigger  conflict detection logic if two agents disagree.

        ttk.Label(self.detail_frame, text="Review status", style="Muted.TLabel").pack(anchor="w")
        status_var = tk.StringVar(value=hazard["status"])
        status_combo = ttk.Combobox(
            self.detail_frame, textvariable=status_var, state="readonly",
            values=["Pending", "Reviewed", "Escalated"],
        )
        status_combo.pack(fill="x", pady=(2, 0))
        status_combo.bind(
            "<<ComboboxSelected>>",
            lambda e, hid=hazard["id"], var=status_var: self._set_status(hid, var.get()),
        )

        self.ai_summary_var.set(hazard["ai_summary"])

    def _set_image_type(self, image_type):
        self.selected_image_type = image_type
        self._render_detail()

    def _set_status(self, hazard_id, new_status):
        hazard = next((h for h in mock_data.HAZARDS if h["id"] == hazard_id), None)
        if hazard:
            hazard["status"] = new_status
            # TODO(link: REQ004): replace this in-memory mutation with a real update call to database.

    def _show_conflict(self):
        # TODO!
        # show  conflict details for the hazards instead (currently using example list, need to use actual data when i have access)
        for conflict in mock_data.CONFLICTS:
            if conflict["resolved"]:
                continue
            message = (
                f"Hazard {conflict['hazard_id']}: "
                f"field agent {conflict['agent_a']} marked '{conflict['status_a']}', "
                f"field agent {conflict['agent_b']} marked '{conflict['status_b']}'.\n\n"
                f"An admin can resolve this from the admin dashboard."
            )
            messagebox.showinfo("Conflicting review", message)

    def _generate_report(self):
        # TODO!
        # update to a real path when AI data available
        hazard_ids = [h["id"] for h in self._filtered_hazards()]
        path = mock_data.generate_pdf_report(hazard_ids)
        messagebox.showinfo("Report generated", f"PDF report generated:\n{path}")