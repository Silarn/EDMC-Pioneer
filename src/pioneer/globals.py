import semantic_version

# TKinter imports
import tkinter as tk
from tkinter import ttk

# Database objects
from sqlalchemy.orm import Session

from ExploData.explo_data.db import Commander, System, SystemStatus
from ExploData.explo_data.body_data.struct import PlanetData, StarData, NonBodyData

# Local imports
import pioneer.const
import pioneer.overlay as overlay
from pioneer.data import BodyValueData
from pioneer.format_util import Formatter

# EDMC imports
from ttkHyperlinkLabel import HyperlinkLabel

class Globals:
    """Holds module globals."""

    def __init__(self):
        self.NAME = pioneer.const.plugin_name
        self.VERSION = semantic_version.Version(pioneer.const.plugin_version)
        self.formatter = Formatter()
        self.overlay = overlay.Overlay()

        self.parent: tk.Frame | None = None
        self.frame: tk.Frame | None = None
        self.scroll_canvas: tk.Canvas | None = None
        self.scrollbar: ttk.Scrollbar | None = None
        self.scrollable_frame: ttk.Frame | None = None
        self.label: tk.Label | None = None
        self.copy_button: tk.Label | None = None
        self.edsm_button: tk.Label | None = None
        self.edsm_failed: tk.Label | None = None
        self.values_label: tk.Label | None = None
        self.total_label: tk.Label | None = None
        self.update_button: HyperlinkLabel | None = None
        self.journal_label: tk.Label | None = None
        self.view_button: tk.Button | None = None
        self.display_hidden: bool = False

        # DB
        self.sql_session: Session | None = None
        self.migration_failed: bool = False
        self.db_mismatch: bool = False

        # Plugin state
        self.odyssey: bool = False
        self.game_version = semantic_version.Version('0.0.0')
        self.commander: Commander | None = None
        self.system: System | None = None
        self.system_status: SystemStatus | None = None
        self.system_was_scanned: bool = False
        self.system_was_mapped: bool = False
        self.system_has_undiscovered: bool = False
        self.current_body_name: str | None = None
        self.overlay_local_text: str | None = None
        self.is_nav_beacon: bool = False
        self.analysis_mode: bool = True
        self.in_flight: bool = False
        self.fsd_jump: bool = False
        self.bodies: dict[str, PlanetData | StarData] = {}
        self.non_bodies: dict[str, NonBodyData] = {}
        self.body_values: dict[str, BodyValueData] = {}
        self.body_sale_status: dict[str, tuple[bool, bool, bool, bool]] = {}
        self.unsold_systems: dict[int, tuple[int, int] | bool] = {}
        self.recalculate_unsold: bool = True
        self.scans = set()
        self.main_star_value: int = 0
        self.main_star_name = ''
        self.main_star_type = 'Star'
        self.map_count: int = 0
        self.planet_count: int = 0
        self.non_body_count: int = 0
        self.belt_count: int = 0
        self.belts_found: int = 0
        self.gui_focus: int = 0

        # Setting vars
        self.min_value: tk.IntVar | None = None
        self.shorten_values: tk.BooleanVar | None = None
        self.show_details: tk.BooleanVar | None = None
        self.show_biological: tk.BooleanVar | None = None
        self.show_descriptors: tk.BooleanVar | None = None
        self.show_carrier_values: tk.BooleanVar | None = None
        self.show_map_counter: tk.BooleanVar | None = None
        self.use_overlay: tk.BooleanVar | None = None
        self.overlay_color: tk.StringVar | None = None
        self.overlay_anchor_x: tk.IntVar | None = None
        self.overlay_anchor_y: tk.IntVar | None = None

pioneer_globals = Globals()