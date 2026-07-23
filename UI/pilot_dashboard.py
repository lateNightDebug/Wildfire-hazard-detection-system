

import tkinter as tk
from tkinter import ttk, filedialog

import styles
import mock_data


class PilotDashboard(ttk.Frame):
    def __init__(self, parent, controller):
        super().__init__(parent, style="App.TFrame")
        self.controller = controller

        self._build_topbar()
        self._build_alert_banner()

        body = ttk.Frame(self, style="App.TFrame", padding=(20, 0, 20, 20))
        body.pack(fill="both", expand=True)

        row = ttk.Frame(body, style="App.TFrame")
        row.pack(fill="x")
        self._build_weather_card(row)
        self._build_airspace_card(row)

        self._build_flight_log_card(body)
        self._build_sync_line(body)

    
    def _build_topbar(self):
        bar = ttk.Frame(self, style="Card.TFrame", padding=(20, 10))
        bar.pack(fill="x")

        left = ttk.Frame(bar, style="Card.TFrame")
        left.pack(side="left")
        ttk.Label(left, text="Flight planning — Kananaskis block 4",
                  style="CardTitle.TLabel").pack(anchor="w")
        ttk.Label(left, text="Drone operator", style="Muted.TLabel").pack(anchor="w")

        right = ttk.Frame(bar, style="Card.TFrame")
        right.pack(side="right")
        ttk.Button(right, text="Upload flight data", style="Secondary.TButton",
                   command=self._upload_flight_data).pack(side="left", padx=(0, 10))
        ttk.Button(right, text="Log out", style="Secondary.TButton",
                   command=lambda: self.controller.show_screen("login")).pack(side="left")

    def _build_alert_banner(self):
        # TODO! 
        # #(link: REQ009): mock_data.get_extreme_weather_alert() shoulpull from real forecast data for the site
        alert_text = mock_data.get_extreme_weather_alert()
        if alert_text:
            banner = tk.Frame(self, bg=styles.WARNING_BG)
            banner.pack(fill="x", padx=20, pady=(12, 0))
            tk.Label(banner, text=alert_text, bg=styles.WARNING_BG,
                     fg=styles.WARNING, font=styles.FONT_BODY,
                     padx=14, pady=8).pack(anchor="w")

    def _build_weather_card(self, parent):
        card = ttk.Frame(parent, style="Card.TFrame", padding=16)
        card.pack(side="left", fill="both", expand=True, padx=(0, 8), pady=16)

        ttk.Label(card, text="Weather at coordinates",
                  style="CardTitle.TLabel").pack(anchor="w")
        ttk.Label(card, text="Enter coordinates to check current conditions.",
                  style="Muted.TLabel").pack(anchor="w", pady=(0, 8))

        # TODO! (link: REQ002): this entry currently just feeds mock_data.get_weather_for_coordinates(), which fakes a response.
        # Replace that function's body with a real weather API call
        self.coords_var = tk.StringVar(value="50.9, -115.1")
        coords_entry = ttk.Entry(card, textvariable=self.coords_var, font=styles.FONT_MONO)
        coords_entry.pack(fill="x", pady=(0, 8))
        coords_entry.bind("<Return>", lambda e: self._lookup_weather())
        coords_entry.bind("<FocusOut>", lambda e: self._lookup_weather())

        result_row = ttk.Frame(card, style="Card.TFrame")
        result_row.pack(fill="x")
        self.weather_temp_label = ttk.Label(result_row, style="Card.TLabel")
        self.weather_temp_label.pack(side="left")
        self.weather_wind_label = ttk.Label(result_row, style="Muted.TLabel")
        self.weather_wind_label.pack(side="right")

        self._lookup_weather()

    def _lookup_weather(self):
        # TODO! 
        # swap mock_data.get_weather_for_coordinates for
        # a real API call.
        data = mock_data.get_weather_for_coordinates(self.coords_var.get())
        self.weather_temp_label.config(text=f"{data['temp_c']}°C, {data['condition']}")
        self.weather_wind_label.config(text=f"Wind {data['wind_kph']} km/h")

    def _build_airspace_card(self, parent):
        card = ttk.Frame(parent, style="Card.TFrame", padding=16)
        card.pack(side="left", fill="both", expand=True, padx=(8, 0), pady=16)

        ttk.Label(card, text="Airspace at coordinates",
                  style="CardTitle.TLabel").pack(anchor="w")
        ttk.Label(card, text="Flight restrictions for the current location.",
                  style="Muted.TLabel").pack(anchor="w", pady=(0, 8))

        # TODO! 
        # real airspace/NOTAM lookup should key off the coordinates as the weather card
        airspace = mock_data.get_airspace_for_coordinates(self.coords_var.get() if hasattr(self, "coords_var") else "")
        ttk.Label(card, text=airspace["classification"],
                  style="Card.TLabel").pack(anchor="w", pady=(0, 6))

        self.airspace_detail_visible = False
        self.airspace_detail_label = ttk.Label(
            card, text=airspace["detail"], style="Muted.TLabel", wraplength=280,
        )
        self.toggle_link = ttk.Label(
            card, text="View full flight restrictions",
            foreground=styles.ACCENT, background=styles.SURFACE,
            font=styles.FONT_LABEL, cursor="hand2",
        )
        self.toggle_link.pack(anchor="w")
        self.toggle_link.bind("<Button-1>", lambda e: self._toggle_airspace_detail())

    def _toggle_airspace_detail(self):
        self.airspace_detail_visible = not self.airspace_detail_visible
        if self.airspace_detail_visible:
            self.airspace_detail_label.pack(anchor="w", pady=(6, 0))
        else:
            self.airspace_detail_label.pack_forget()

    def _build_flight_log_card(self, parent):
        card = ttk.Frame(parent, style="Card.TFrame", padding=16)
        card.pack(fill="x", pady=(0, 16))

        ttk.Label(card, text="Flight log", style="CardTitle.TLabel").pack(anchor="w")
        ttk.Label(card, text="Recent uploads for this site.",
                  style="Muted.TLabel").pack(anchor="w", pady=(0, 8))

        # TODO! 
        # mock_data.FLIGHT_LOG is a hard-coded list replace with a real query
        for entry in mock_data.FLIGHT_LOG:
            sync_text = "synced" if entry["synced"] else "pending sync"
            ttk.Label(
                card, style="Muted.TLabel",
                text=f"{entry['date']} — {entry['image_count']} images — {sync_text}",
            ).pack(anchor="w", pady=1)

    def _build_sync_line(self, parent):
        # TODO!
        # mock_data.SYNC_STATUS_TEXT should be buil from real syncs
        ttk.Label(parent, text=mock_data.SYNC_STATUS_TEXT,
                  style="Muted.TLabel").pack(anchor="w")

    def _upload_flight_data(self):
        # TODO!
        # this just opens a file picker and does nothing with the result. Replace with real logic to send the selected flight data
        filedialog.askopenfilename(title="Select flight data to upload")
