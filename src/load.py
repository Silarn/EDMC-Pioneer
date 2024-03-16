# -*- coding: utf-8 -*-
# Pioneer (System Value) plugin for EDMC
# Source: https://github.com/Silarn/EDMC-Pioneer
# Inspired by Economical Cartographics: https://github.com/n-st/EDMC-EconomicalCartographics
# Licensed under the [GNU Public License (GPL)](http://www.gnu.org/licenses/gpl-2.0.html) version 2 or later.
import os
import re

import requests
import semantic_version
import sys
from traceback import print_exc
from typing import Any, MutableMapping, Mapping

import tkinter as tk
from tkinter import ttk, colorchooser as tkColorChooser, Widget as tkWidget
from ttkHyperlinkLabel import HyperlinkLabel
from sqlalchemy import select
from sqlalchemy.orm import Session

import myNotebook as nb
import plug
from config import config
from theme import theme
from EDMCLogging import get_plugin_logger

import ExploData
from ExploData.explo_data import db
from ExploData.explo_data.db import System, Commander, SystemStatus, Metadata
from ExploData.explo_data.RegionMap import findRegion
from ExploData.explo_data.body_data.struct import PlanetData, StarData, load_planets, load_stars, get_main_star, \
    NonBodyData, load_non_bodies
from ExploData.explo_data.journal_parse import register_event_callbacks, parse_journals, register_journal_callbacks

import pioneer.const
from pioneer.overlay import Overlay
from pioneer.data import BodyValueData
from pioneer.util import get_star_label, get_body_shorthand
from pioneer.body_calc import get_body_value, get_star_value, get_starclass_k, get_planetclass_k
from pioneer.format_util import Formatter

efficiency_bonus = 1.25


class This:
    """Holds module globals."""

    def __init__(self):
        self.NAME = pioneer.const.plugin_name
        self.VERSION = semantic_version.Version(pioneer.const.plugin_version)
        self.formatter = Formatter()
        self.overlay = Overlay()

        self.parent: tk.Frame | None = None
        self.frame: tk.Frame | None = None
        self.scroll_canvas: tk.Canvas | None = None
        self.scrollbar: ttk.Scrollbar | None = None
        self.scrollable_frame: ttk.Frame | None = None
        self.label: tk.Label | None = None
        self.copy_button: tk.Label | None = None
        self.values_label: tk.Label | None = None
        self.total_label: tk.Label | None = None
        self.update_button: HyperlinkLabel | None = None
        self.journal_label: tk.Label | None = None

        # DB
        self.sql_session: Session | None = None
        self.migration_failed: bool = False
        self.db_mismatch: bool = False

        # Plugin state
        self.odyssey = False
        self.game_version = semantic_version.Version('0.0.0')
        self.commander: Commander | None = None
        self.system: System | None = None
        self.system_status: SystemStatus | None = None
        self.system_was_scanned = False
        self.system_was_mapped = False
        self.bodies: dict[str, PlanetData | StarData] = {}
        self.non_bodies: dict[str, NonBodyData] = {}
        self.body_values: dict[str, BodyValueData] = {}
        self.scans = set()
        self.main_star_value: int = 0
        self.main_star_name = ''
        self.main_star_type = 'Star'
        self.map_count: int = 0
        self.planet_count: int = 0
        self.non_body_count: int = 0

        # Setting vars
        self.min_value: tk.IntVar | None = None
        self.shorten_values: tk.BooleanVar | None = None
        self.show_details: tk.BooleanVar | None = None
        self.show_biological: tk.BooleanVar | None = None
        self.show_descriptors: tk.BooleanVar | None = None
        self.show_carrier_values: tk.BooleanVar | None = None
        self.use_overlay: tk.BooleanVar | None = None
        self.overlay_color: tk.StringVar | None = None
        self.overlay_anchor_x: tk.IntVar | None = None
        self.overlay_anchor_y: tk.IntVar | None = None


this = This()
logger = get_plugin_logger(this.NAME)


def plugin_start3(plugin_dir: str) -> str:
    """
    EDMC start hook.
    Initializes SQLite database.

    :param plugin_dir: The plugin's directory
    :return: The plugin's canonical name
    """

    this.migration_failed = db.init()
    if not this.migration_failed:
        this.sql_session = Session(db.get_engine())
        db_version: Metadata = this.sql_session.scalar(select(Metadata).where(Metadata.key == 'version'))
        if db_version.value.isdigit() and int(db_version.value) > pioneer.const.db_version:
            this.db_mismatch = True

        if not this.db_mismatch:
            register_event_callbacks(
                {'Scan', 'FSSDiscoveryScan', 'FSSAllBodiesFound', 'SAAScanComplete'},
                process_data_event
            )
    return this.NAME


def plugin_stop() -> None:
    """
    EDMC plugin stop function. Closes open threads and database sessions for clean shutdown.
    """

    if this.overlay.available():
        this.overlay.disconnect()


def version_check() -> str:
    try:
        req = requests.get(url='https://api.github.com/repos/Silarn/EDMC-Pioneer/releases/latest')
        data = req.json()
        if req.status_code != requests.codes.ok:
            raise requests.RequestException
    except requests.RequestException | requests.JSONDecodeError:
        print_exc()
        return ''

    version = semantic_version.Version(data['tag_name'][1:])
    if version > this.VERSION:
        return str(version)
    return ''


def plugin_app(parent: tk.Frame) -> tk.Frame:
    """
    EDMC initialization hook.
    Build TKinter display pane and initialize display attributes.

    :param parent: EDMC parent TKinter frame
    :return: Plugin's main TKinter frame
    """

    this.parent = parent
    this.frame = tk.Frame(parent)
    this.frame.grid_columnconfigure(0, weight=1)
    if this.migration_failed:
        this.label = tk.Label(this.frame, text='Pioneer: DB Migration Failed')
        this.label.grid(row=0, sticky=tk.EW)
        this.update_button = HyperlinkLabel(this.frame, text='Please Check or Submit an Issue',
                                            url='https://github.com/Silarn/EDMC-Pioneer/issues')
        this.update_button.grid(row=1, columnspan=2, sticky=tk.N)
    elif this.db_mismatch:
        this.label = tk.Label(this.frame, text='Pioneer: Database Mismatch')
        this.label.grid(row=0, sticky=tk.EW)
        this.update_button = HyperlinkLabel(this.frame, text='You May Need to Update',
                                            url='https://github.com/Silarn/EDMC-Pioneer/releases/latest')
        this.update_button.grid(row=1, columnspan=2, sticky=tk.N)
    else:
        parse_config()
        if not len(sorted(plug.PLUGINS, key=lambda item: item.name == 'BioScan')):  # type: list[plug.Plugin]
            register_journal_callbacks(this.frame, 'pioneer', journal_start, journal_update, journal_end)
        this.label = tk.Label(this.frame)
        this.label.grid(row=0, column=0, columnspan=2, sticky=tk.N)
        this.scroll_canvas = tk.Canvas(this.frame, height=100, highlightthickness=0)
        this.scrollbar = ttk.Scrollbar(this.frame, orient='vertical', command=this.scroll_canvas.yview)
        this.scrollable_frame = ttk.Frame(this.scroll_canvas)
        this.scrollable_frame.bind(
            '<Configure>',
            lambda e: this.scroll_canvas.configure(
                scrollregion=this.scroll_canvas.bbox('all')
            )
        )
        this.scroll_canvas.bind('<Enter>', bind_mousewheel)
        this.scroll_canvas.bind('<Leave>', unbind_mousewheel)
        this.scroll_canvas.create_window((0, 0), window=this.scrollable_frame, anchor='nw')
        this.scroll_canvas.configure(yscrollcommand=this.scrollbar.set)
        this.values_label = ttk.Label(this.scrollable_frame, wraplength=360, justify=tk.LEFT)
        this.values_label.pack(fill=tk.BOTH, side=tk.LEFT)
        this.scroll_canvas.grid(row=1, column=0, sticky=tk.EW)
        this.scroll_canvas.grid_rowconfigure(1, weight=0)
        this.scrollbar.grid(row=1, column=1, sticky=tk.NSEW)
        this.total_label = tk.Label(this.frame)
        this.total_label.grid(row=2, column=0, columnspan=2, sticky=tk.N)
        this.journal_label = tk.Label(this.frame, text='Journal Parsing')
        update = version_check()
        if update != '':
            text = 'Version {} is now available'.format(update)
            url = 'https://github.com/Silarn/EDMC-Pioneer/releases/tag/v{}'.format(update)
            this.update_button = HyperlinkLabel(this.frame, text=text, url=url)
            this.update_button.grid(row=3, columnspan=2, sticky=tk.N)
        this.copy_button = tk.Label(this.frame, text='Export', fg='white', cursor='hand2')
        this.copy_button.grid(row=4, columnspan=2, sticky=tk.EW)
        this.copy_button.bind('<Button-1>', lambda e: export_text())
        update_display()
        theme.register(this.values_label)
    return this.frame


def validate_int(val: str) -> bool:
    if val.isdigit() or val == '':
        return True
    return False


def export_text() -> None:
    export_path = config.app_dir_path / 'pioneer_exports'
    if not export_path.exists():
        os.makedirs(export_path)
    filename = re.sub(r'[^\w\s-]', '', this.system.name)
    filename = re.sub(r'[-\s]+', '-', filename).strip('-_')
    filename += '.txt'
    file = open(export_path / filename, 'w')
    file.write(this.values_label['text'] + '\n')
    file.write(this.total_label['text'])
    file.close()


def plugin_prefs(parent: nb.Frame, cmdr: str, is_beta: bool) -> nb.Frame:
    """
    EDMC settings pane hook.
    Build settings display and hook in settings properties.

    :param parent: EDMC parent settings pane TKinter frame
    :param cmdr: Commander name (unused)
    :param is_beta: ED beta status (unused)
    :return: Plugin settings tab TKinter frame
    """

    color_button = None

    def color_chooser() -> None:
        (_, color) = tkColorChooser.askcolor(
            this.overlay_color.get(), title='Overlay Color', parent=this.parent
        )

        if color:
            this.overlay_color.set(color)
            if color_button is not None:
                color_button['foreground'] = color

    x_padding = 10
    x_button_padding = 12
    y_padding = 2
    frame = nb.Frame(parent)
    frame.columnconfigure(2, weight=1)
    frame.rowconfigure(60, weight=1)

    title_frame = nb.Frame(frame)
    title_frame.grid(row=1, columnspan=3, sticky=tk.NSEW)
    title_frame.columnconfigure(0, weight=1)
    HyperlinkLabel(title_frame, text=this.NAME, background=nb.Label().cget('background'),
                   url='https://github.com/Silarn/EDMC-Pioneer', underline=True) \
        .grid(row=0, padx=x_padding, sticky=tk.W)
    nb.Label(title_frame, text='Version %s' % this.VERSION) \
        .grid(row=0, column=1, sticky=tk.E)
    nb.Label(title_frame, text='Data Version: %s' % pioneer.const.db_version) \
        .grid(row=0, column=2, padx=x_padding, sticky=tk.E)
    HyperlinkLabel(title_frame, text=ExploData.explo_data.const.plugin_name, background=nb.Label().cget('background'),
                   url='https://github.com/Silarn/EDMC-ExploData', underline=True) \
        .grid(row=1, padx=x_padding, pady=y_padding * 2, sticky=tk.W)
    nb.Label(title_frame, text='Version %s' % semantic_version.Version(ExploData.explo_data.const.plugin_version)) \
        .grid(row=1, column=1, pady=y_padding * 2, sticky=tk.E)
    nb.Label(title_frame, text='Data Version: %s' % ExploData.explo_data.const.database_version) \
        .grid(row=1, column=2, padx=x_padding, pady=y_padding * 2, sticky=tk.E)

    ttk.Separator(frame).grid(row=5, columnspan=3, pady=y_padding*2, sticky=tk.EW)
    nb.Label(frame, text='Valuable Body Minimum:').grid(row=10, column=0, padx=x_padding, sticky=tk.W)
    vcmd = (frame.register(validate_int))
    nb.Entry(frame, textvariable=this.min_value,
             validate='all', validatecommand=(vcmd, '%P')).grid(row=10, column=1, sticky=tk.W)
    nb.Label(frame, text='Cr').grid(row=10, column=2, sticky=tk.W)
    nb.Checkbutton(
        frame,
        text='Shorten credit values (thousands, millions)',
        variable=this.shorten_values
    ).grid(row=15, columnspan=3, padx=x_button_padding, sticky=tk.W)
    nb.Checkbutton(
        frame,
        text='Show detailed body values (scrollbox)',
        variable=this.show_details
    ).grid(row=20, columnspan=3, padx=x_button_padding, sticky=tk.W)
    nb.Checkbutton(
        frame,
        text='Show unmapped bodies with biological signals',
        variable=this.show_biological
    ).grid(row=25, columnspan=3, padx=x_button_padding, sticky=tk.W)
    nb.Checkbutton(
        frame,
        text='Show additional star descriptors',
        variable=this.show_descriptors
    ).grid(row=30, columnspan=3, padx=x_button_padding, sticky=tk.W)
    nb.Checkbutton(
        frame,
        text='Show carrier values',
        variable=this.show_carrier_values
    ).grid(row=31, columnspan=3, padx=x_button_padding, sticky=tk.W)

    # Overlay settings
    ttk.Separator(frame).grid(row=35, columnspan=3, pady=y_padding*2, sticky=tk.EW)

    nb.Label(frame,
             text='EDMC Overlay Integration',
             justify=tk.LEFT) \
        .grid(row=40, column=0, padx=x_padding, sticky=tk.NW)
    nb.Checkbutton(
        frame,
        text='Enable overlay',
        variable=this.use_overlay
    ).grid(row=41, column=0, padx=x_button_padding, pady=0, sticky=tk.W)
    color_button = nb.ColoredButton(
        frame,
        text='Text Color',
        foreground=this.overlay_color.get(),
        background='grey4',
        command=lambda: color_chooser()
    ).grid(row=42, column=0, padx=x_button_padding, pady=y_padding, sticky=tk.W)

    anchor_frame = nb.Frame(frame)
    anchor_frame.grid(row=41, column=1, sticky=tk.NSEW)
    anchor_frame.columnconfigure(4, weight=1)

    nb.Label(anchor_frame, text='Display Anchor:') \
        .grid(row=0, column=0, sticky=tk.W)
    nb.Label(anchor_frame, text='X') \
        .grid(row=0, column=1, sticky=tk.W)
    nb.Entry(
        anchor_frame, text=this.overlay_anchor_x.get(), textvariable=this.overlay_anchor_x,
        width=8, validate='all', validatecommand=(vcmd, '%P')
    ).grid(row=0, column=2, sticky=tk.W)
    nb.Label(anchor_frame, text='Y') \
        .grid(row=0, column=3, sticky=tk.W)
    nb.Entry(
        anchor_frame, text=this.overlay_anchor_y.get(), textvariable=this.overlay_anchor_y,
        width=8, validate='all', validatecommand=(vcmd, '%P')
    ).grid(row=0, column=4, sticky=tk.W)

    ttk.Separator(frame, orient=tk.HORIZONTAL).grid(row=55, columnspan=3, pady=y_padding*2, sticky=tk.EW)

    nb.Button(frame, text='Start / Stop Journal Parsing', command=parse_journals) \
        .grid(row=60, column=0, padx=x_padding, sticky=tk.SW)
    return frame


def prefs_changed(cmdr: str, is_beta: bool) -> None:
    config.set('pioneer_min_value', this.min_value.get())
    config.set('pioneer_shorten', this.shorten_values.get())
    this.formatter.set_shorten(this.shorten_values.get())
    config.set('pioneer_details', this.show_details.get())
    config.set('pioneer_biological', this.show_biological.get())
    config.set('pioneer_star_descriptors', this.show_descriptors.get())
    config.set('pioneer_carrier_values', this.show_carrier_values.get())
    config.set('pioneer_overlay', this.use_overlay.get())
    config.set('pioneer_overlay_color', this.overlay_color.get())
    config.set('pioneer_overlay_anchor_x', this.overlay_anchor_x.get())
    config.set('pioneer_overlay_anchor_y', this.overlay_anchor_y.get())
    update_display()


def parse_config() -> None:
    this.min_value = tk.IntVar(value=config.get_int(key='pioneer_min_value', default=400000))
    this.shorten_values = tk.BooleanVar(value=config.get_bool(key='pioneer_shorten', default=True))
    this.formatter.set_shorten(this.shorten_values.get())
    this.show_details = tk.BooleanVar(value=config.get_bool(key='pioneer_details', default=True))
    this.show_biological = tk.BooleanVar(value=config.get_bool(key='pioneer_biological', default=True))
    this.show_descriptors = tk.BooleanVar(value=config.get_bool(key='pioneer_star_descriptors', default=False))
    this.show_carrier_values = tk.BooleanVar(value=config.get_bool(key='pioneer_carrier_values', default=False))
    this.use_overlay = tk.BooleanVar(value=config.get_bool(key='pioneer_overlay', default=False))
    this.overlay_color = tk.StringVar(value=config.get_str(key='pioneer_overlay_color', default='#ffffff'))
    this.overlay_anchor_x = tk.IntVar(value=config.get_int(key='pioneer_overlay_anchor_x', default=1000))
    this.overlay_anchor_y = tk.IntVar(value=config.get_int(key='pioneer_overlay_anchor_y', default=225))


def journal_start(event: tk.Event) -> None:
    """
    Event handler for the start of journal processing. Adds the progress line to the display.

    :param event: Required to process the event. Unused.
    """

    this.journal_label.grid(row=4, columnspan=2, sticky=tk.EW)
    this.journal_label['text'] = 'Parsing Journals: 0%'


def journal_update(event: tk.Event) -> None:
    """
    Event handler for journal processing progress updates. Updates the display with the current progress.

    :param event: Required to process the event. Unused.
    """

    finished, total = ExploData.explo_data.journal_parse.get_progress()
    progress = '0%'
    if total > 0:
        progress = f'{finished / total:.1%}'
    progress = progress.rstrip('0').rstrip('.')
    this.journal_label['text'] = f'Parsing Journals: {progress} [{finished}/{total}]'


def journal_end(event: tk.Event) -> None:
    """
    Event handler for journal processing completion. Removes the display or reports an error.

    :param event: Required to process the event. Unused.
    """

    if ExploData.explo_data.journal_parse.has_error():
        this.journal_label['text'] = 'Error During Journal Parse\nPlease Submit a Report'
    else:
        this.journal_label.grid_remove()
        this.bodies = load_planets(this.system, this.sql_session) | load_stars(this.system, this.sql_session)
        this.non_bodies = load_non_bodies(this.system, this.sql_session)
        for body in this.bodies.values():
            process_body_values(body)
        update_display()


def calc_system_value() -> tuple[int, int, int, int]:
    if not this.main_star_value:
        this.values_label['text'] = 'Main star not scanned.\nSystem already visited?'
        return 0, 0, 0, 0
    max_value = this.main_star_value
    min_max_value = this.main_star_value
    value_sum = this.main_star_value
    min_value_sum = this.main_star_value
    honk_sum, min_honk_sum = 0, 0
    bodies_text = ''
    for body_name, body_data in sorted(this.bodies.items(), key=lambda item: item[1].get_id()):
        is_range = this.body_values[body_name].get_mapped_values()[1] != \
                   this.body_values[body_name].get_mapped_values()[0]
        bodies_text += '{} - {}{}{}{}:'.format(
            body_name,
            body_data.get_type() if type(body_data) is PlanetData else
            get_star_label(body_data.get_type(),
                           body_data.get_subclass(),
                           body_data.get_luminosity(),
                           this.show_descriptors.get()),
            ' <TC>' if type(body_data) is PlanetData and body_data.is_terraformable() else '',
            ' -S-' if body_data.was_discovered(this.commander.id) else '',
            ' -M-' if type(body_data) is PlanetData and body_data.was_mapped(this.commander.id) else '',
        ) + '\n'
        if type(body_data) is PlanetData and body_data.is_mapped(this.commander.id):
            efficiency = efficiency_bonus if body_data.was_efficient(this.commander.id) else 1
            val_text = '{} - {}'.format(
                this.formatter.format_credits(this.body_values[body_name].get_mapped_values()[1] * efficiency),
                this.formatter.format_credits(this.body_values[body_name].get_mapped_values()[0] * efficiency)) \
                if is_range else \
                '{}'.format(this.formatter.format_credits(
                    this.body_values[body_name].get_mapped_values()[0] * efficiency
                ))
            bodies_text += 'Current Value (Max): {}\n'.format(val_text)
            if body_data.was_efficient(this.commander.id):
                bodies_text += '  (Efficient)\n'
            if this.show_carrier_values.get():
                bodies_text += 'Carrier Value: {}{} ({} -> carrier)\n'.format(
                    'Up to ' if is_range else '',
                    this.formatter.format_credits(int(this.body_values[body_name].get_mapped_values()[0] * efficiency * .75)),
                    this.formatter.format_credits(int(this.body_values[body_name].get_mapped_values()[0] * efficiency * .125))
                )
            max_value += this.body_values[body_name].get_mapped_values()[0] * efficiency
            min_max_value += this.body_values[body_name].get_mapped_values()[1] * efficiency
            value_sum += this.body_values[body_name].get_mapped_values()[0] * efficiency
            min_value_sum += this.body_values[body_name].get_mapped_values()[1] * efficiency
        elif type(body_data) is PlanetData:
            val_text = '{} - {}'.format(
                this.formatter.format_credits(this.body_values[body_name].get_base_values()[1]),
                this.formatter.format_credits(this.body_values[body_name].get_base_values()[0])) \
                if is_range else \
                '{}'.format(this.formatter.format_credits(this.body_values[body_name].get_base_values()[0]))
            max_val_text = '{} - {}'.format(
                this.formatter.format_credits(int(this.body_values[body_name].get_mapped_values()[1] * efficiency_bonus)),
                this.formatter.format_credits(int(this.body_values[body_name].get_mapped_values()[0] * efficiency_bonus))
            ) if is_range else '{}'.format(
                this.formatter.format_credits(int(this.body_values[body_name].get_mapped_values()[0] * efficiency_bonus))
            )
            bodies_text += 'Current Value: {}\n'.format(val_text)
            if this.show_carrier_values.get():
                bodies_text += 'Carrier Value: {}{} ({} -> carrier)\n'.format(
                    'Up to ' if is_range else '',
                    this.formatter.format_credits(int(this.body_values[body_name].get_base_values()[0] * .75)),
                    this.formatter.format_credits(int(this.body_values[body_name].get_base_values()[0] * .125))
                )
            bodies_text += 'Max Value: {}\n'.format(max_val_text)
            max_value += int(this.body_values[body_name].get_mapped_values()[0] * efficiency_bonus)
            min_max_value += int(this.body_values[body_name].get_mapped_values()[1] * efficiency_bonus)
            value_sum += this.body_values[body_name].get_base_values()[0]
            min_value_sum += this.body_values[body_name].get_base_values()[1]
        else:
            val_text = '{} - {}'.format(
                this.formatter.format_credits(this.body_values[body_name].get_base_values()[1]),
                this.formatter.format_credits(this.body_values[body_name].get_base_values()[0])) \
                if is_range else '{}'.format(
                    this.formatter.format_credits(this.body_values[body_name].get_base_values()[0])
                )
            bodies_text += 'Current Value (Max): {}\n'.format(val_text)
            if this.show_carrier_values.get():
                bodies_text += 'Carrier Value: {}{} ({} -> carrier)\n'.format(
                    'Up to ' if is_range else '',
                    this.formatter.format_credits(int(this.body_values[body_name].get_base_values()[0] * .75)),
                    this.formatter.format_credits(int(this.body_values[body_name].get_base_values()[0] * .125))
                )
            max_value += this.body_values[body_name].get_base_values()[0]
            min_max_value += this.body_values[body_name].get_base_values()[1]
            value_sum += this.body_values[body_name].get_base_values()[0]
            min_value_sum += this.body_values[body_name].get_base_values()[1]
        if get_system_status().honked:
            if this.body_values[body_name].get_honk_values()[0] != this.body_values[body_name].get_honk_values()[1]:
                bodies_text += 'Honk Value: {} - {}'.format(
                    this.formatter.format_credits(this.body_values[body_name].get_honk_values()[1]),
                    this.formatter.format_credits(this.body_values[body_name].get_honk_values()[0])) + '\n'
            else:
                bodies_text += 'Honk Value: {}'.format(
                    this.formatter.format_credits(this.body_values[body_name].get_honk_values()[0])
                ) + '\n'
            value_sum += this.body_values[body_name].get_honk_values()[0]
            min_value_sum += this.body_values[body_name].get_honk_values()[1]
            honk_sum += this.body_values[body_name].get_honk_values()[0]
            min_honk_sum += this.body_values[body_name].get_honk_values()[1]
        max_value += this.body_values[body_name].get_honk_values()[0]
        min_max_value += this.body_values[body_name].get_honk_values()[1]
        bodies_text += '------------------' + '\n'
    this.values_label['text'] = '{}:\n   {}\n   {} + {} = {}\n'.format(
        this.main_star_name,
        this.main_star_type,
        this.formatter.format_credits(this.main_star_value),
        this.formatter.format_credits(honk_sum) if honk_sum == min_honk_sum else '{} to {}'.format(
            this.formatter.format_credits(min_honk_sum),
            this.formatter.format_credits(honk_sum)
        ),
        (this.formatter.format_credits(this.main_star_value + honk_sum)) if honk_sum == min_honk_sum else '{} to {}'.format(
            this.formatter.format_credits(this.main_star_value + min_honk_sum),
            this.formatter.format_credits(this.main_star_value + honk_sum)
        ))
    if this.show_carrier_values.get():
        is_range = honk_sum != min_honk_sum
        this.values_label['text'] += '   Carrier: {}{} ({} -> carrier)\n'.format(
            'Up to ' if is_range else '',
            this.formatter.format_credits(int((this.main_star_value + honk_sum) * .75)),
            this.formatter.format_credits(int((this.main_star_value + honk_sum) * .125))
        )
    this.values_label['text'] += '------------------' + '\n'
    this.values_label['text'] += bodies_text
    status = get_system_status()
    if not this.system_was_scanned:
        total_bodies = this.non_body_count + this.system.body_count
        if status.fully_scanned:
            this.values_label['text'] += 'Fully Scanned Bonus: {}'.format(
                this.formatter.format_credits(total_bodies * 1000)
            ) + '\n'
            value_sum += total_bodies * 1000
            min_value_sum += total_bodies * 1000
        max_value += total_bodies * 1000
        min_max_value += total_bodies * 1000
    if not this.system_was_mapped and this.planet_count > 0:
        if status.fully_scanned and this.planet_count == this.map_count:
            this.values_label['text'] += 'Fully Mapped Bonus: {}'.format(
                this.formatter.format_credits(this.planet_count * 10000)) + '\n'
            value_sum += this.planet_count * 10000
            min_value_sum += this.planet_count * 10000
        max_value += this.planet_count * 10000
        min_max_value += this.planet_count * 10000
    this.scroll_canvas.configure(width=100)
    tkWidget.nametowidget(this.frame, name=this.frame.winfo_parent()).update()
    label_width = this.values_label.winfo_width()
    full_width = this.label.winfo_width() - this.scrollbar.winfo_width()
    final_width = label_width if label_width > full_width else full_width
    this.scroll_canvas.configure(width=final_width)
    return value_sum, min_value_sum, max_value, min_max_value


def get_body_name(fullname: str = '') -> str:
    if fullname.startswith(this.system.name + ' '):
        body_name = fullname[len(this.system.name + ' '):]
    else:
        body_name = fullname
    return body_name


def reset() -> None:
    """
    Reset system data, typically when the location changes
    """

    this.main_star_value = 0
    this.main_star_type = 'Star'
    this.main_star_name = ''
    this.bodies = {}
    this.body_values = {}
    this.non_bodies = {}
    this.honked = False
    this.system_was_scanned = False
    this.system_was_mapped = False
    this.planet_count = 0
    this.map_count = 0
    this.scans = set()


def journal_entry(cmdr: str, is_beta: bool, system: str, station: str,
                  entry: MutableMapping[str, Any], state: Mapping[str, Any]) -> str:
    if entry['event'] == 'Harness-Version':
        this.edmc_wait = True
    if entry['event'] == 'ReplayOver':
        this.edmc_wait = False

    if this.migration_failed:
        return ''

    game_version = semantic_version.Version.coerce(state.get('GameVersion', '0.0.0'))
    odyssey = state.get('Odyssey', False)
    if game_version != this.game_version or odyssey != this.odyssey:
        this.game_version = game_version
        this.odyssey = odyssey
        for body in this.bodies.values():
            process_body_values(body)

    system_changed = False
    if not state['StarPos']:
        return ''

    if cmdr and not this.commander:
        stmt = select(Commander).where(Commander.name == cmdr)
        result = this.sql_session.scalars(stmt)
        this.commander = result.first()
        if not this.commander:
            this.commander = Commander(name=cmdr)
            this.sql_session.add(this.commander)
            this.sql_session.commit()

    if system and (not this.system or system != this.system.name):
        reset()
        system_changed = True
        this.system = this.sql_session.scalar(select(System).where(System.name == system))
        if not this.system:
            this.system = System(name=system)
            this.sql_session.add(this.system)
            this.system.x = state['StarPos'][0]
            this.system.y = state['StarPos'][1]
            this.system.z = state['StarPos'][2]
            sector = findRegion(this.system.x, this.system.y, this.system.z)
            this.system.region = sector[0] if sector is not None else None
        this.bodies = load_planets(this.system, this.sql_session) | load_stars(this.system, this.sql_session)
        this.non_bodies = load_non_bodies(this.system, this.sql_session)
        for body in this.bodies.values():
            process_body_values(body)
        main_star = get_main_star(this.system, this.sql_session)
        if main_star:
            this.main_star_name = 'Main star' if this.system == main_star.name \
                else '{} (Main star)'.format(main_star.name)
            this.main_star_type = get_star_label(main_star.type, main_star.subclass,
                                                 main_star.luminosity, this.show_descriptors.get())
            this.bodies.pop(main_star.name, None)

    if not this.system or not this.commander:
        return ''

    this.sql_session.commit()

    if system_changed:
        this.scroll_canvas.yview_moveto(0.0)

    if this.system:
        calc_counts()
        update_display()

    return ''  # No error


def process_data_event(entry: Mapping[str, Any]) -> None:
    this.sql_session.commit()
    match entry['event']:
        case 'Scan':
            body_short_name = get_body_name(entry['BodyName'])
            body = None
            if 'StarType' in entry:
                body = StarData.from_journal(this.system, body_short_name, entry['BodyID'], this.sql_session)
            elif 'PlanetClass' in entry:
                body = PlanetData.from_journal(this.system, body_short_name, entry['BodyID'], this.sql_session)
            else:
                non_body = NonBodyData.from_journal(this.system, body_short_name, entry['BodyID'], this.sql_session)
                if body_short_name.find('Belt Cluster') != -1:
                    this.non_bodies[body_short_name] = non_body
            process_body_values(body)
            update_display()
        case 'FSSDiscoveryScan':
            if entry['Progress'] == 1.0 and not get_system_status().fully_scanned:
                get_system_status().fully_scanned = True
                this.sql_session.commit()
            update_display()
        case 'FSSAllBodiesFound':
            update_display()
        case 'SAAScanComplete':
            body_short_name = get_body_name(entry['BodyName'])
            if body_short_name.endswith('Ring') or body_short_name.find('Belt Cluster') != -1:
                return
            if body_short_name in this.bodies:
                this.bodies[body_short_name].refresh()
            else:
                this.bodies[body_short_name] = PlanetData.from_journal(this.system, body_short_name,
                                                                       entry['BodyID'], this.sql_session)
            update_display()
    calc_counts()


def calc_counts() -> None:
    this.planet_count = 0
    this.map_count = 0
    this.non_body_count = len(this.non_bodies)
    for body in this.bodies.values():
        if type(body) is PlanetData:
            this.planet_count += 1
            if body.is_mapped(this.commander.id):
                this.map_count += 1

    if len(this.bodies) > this.system.body_count and not get_system_status().honked:
        this.system.body_count = len(this.bodies)
        this.sql_session.commit()


def process_body_values(body: PlanetData | StarData | None) -> None:
    if not body:
        return

    if type(body) is StarData:
        k = get_starclass_k(body.get_type())
        value, honk_value = get_star_value(k, body.get_mass(), not body.was_discovered(this.commander.id))
        if body.get_distance() == 0.0:
            this.main_star_value = value
            this.main_star_name = 'Main star' if this.system.name == body.get_name() \
                else '{} (Main star)'.format(body.get_name())
            this.main_star_type = get_star_label(body.get_type(), body.get_subclass(),
                                                 body.get_luminosity(), this.show_descriptors.get())
        else:
            body_value = BodyValueData(body.get_name(), body.get_id())
            body_value.set_base_values(value, value).set_mapped_values(value, value) \
                .set_honk_values(honk_value, honk_value)
            this.body_values[body.get_name()] = body_value

        if body.was_discovered(this.commander.id):
            this.system_was_scanned = True

    if type(body) is PlanetData:
        odyssey_bonus = this.odyssey or this.game_version.major >= 4
        if body.get_name() not in this.body_values or this.body_values[body.get_name()].get_base_values()[0] == 0:
            this.system_was_scanned = True if body.was_discovered(this.commander.id) else this.system_was_scanned
            this.system_was_mapped = True if body.was_mapped(this.commander.id) else this.system_was_mapped

            k, kt, tm = get_planetclass_k(body.get_type(), body.is_terraformable())
            value, mapped_value, honk_value, \
                min_value, min_mapped_value, min_honk_value = \
                get_body_value(k, kt, tm, body.get_mass(), not body.was_discovered(this.commander.id),
                               not body.was_mapped(this.commander.id), odyssey_bonus)

            if body.get_name() not in this.body_values:
                body_value = BodyValueData(body.get_name(), body.get_id())
            else:
                body_value = this.body_values[body.get_name()]

            body_value.set_base_values(value, min_value).set_honk_values(honk_value, min_honk_value)
            body_value.set_mapped_values(int(mapped_value), int(min_mapped_value))
            this.body_values[body.get_name()] = body_value

    if body.get_distance() > 0.0:
        this.bodies[body.get_name()] = body


def get_system_status() -> SystemStatus | None:
    if not this.system:
        this.system_status = None
    elif this.system_status and this.system_status.system_id != this.system.id:
        this.system_status = None

    if not this.system_status and this.system:
        statuses: list[SystemStatus] = this.system.statuses
        statuses = list(filter(lambda item: item.commander_id == this.commander.id, statuses))
        if len(statuses):
            this.system_status = statuses[0]
        else:
            this.system_status = SystemStatus(system_id=this.system.id, commander_id=this.commander.id)
            this.system.statuses.append(this.system_status)
            this.sql_session.commit()
    return this.system_status


def update_display() -> None:
    system_status = get_system_status()
    if not system_status:
        this.label['text'] = 'Pioneer: Waiting for Data'
        this.scroll_canvas.grid_remove()
        this.scrollbar.grid_remove()
        this.total_label.grid_remove()
        return
    else:
        if this.show_details.get():
            this.scroll_canvas.grid()
            this.scrollbar.grid()
        else:
            this.scroll_canvas.grid_remove()
            this.scrollbar.grid_remove()
        this.total_label.grid()

    valuable_body_names = [
        body_name
        for body_name, body_data
        in sorted(
            this.bodies.items(),
            key=lambda item: item[1].get_distance()
        )
        if type(body_data) is PlanetData
        and this.body_values[body_name].get_mapped_values()[0] * efficiency_bonus >= this.min_value.get()
        and not body_data.is_mapped(this.commander.id)
    ]
    exobio_body_names = [
        '%s (%d)' % (body_name, body_data.get_bio_signals())
        for body_name, body_data
        in sorted(
            this.bodies.items(),
            key=lambda item: item[1].get_distance()
        )
        if type(body_data) is PlanetData and body_data.get_bio_signals() > 0
        and not body_data.is_mapped(this.commander.id)
    ]

    def format_body(body_name: str) -> str:
        # template: NAME (VALUE, DIST), …
        body_value = int(this.body_values[body_name].get_mapped_values()[0] * efficiency_bonus)
        body_distance = this.bodies[body_name].get_distance()
        if body_value >= this.min_value.get():
            return '%s%s (max %s, %s)' % \
                   (body_name,
                    get_body_shorthand(this.bodies[body_name], this.commander.id),
                    this.formatter.format_credits(body_value, False),
                    this.formatter.format_ls(body_distance))
        else:
            return '%s'

    if this.bodies or this.main_star_value > 0:
        if system_status.fully_scanned and len(this.bodies) + 1 >= this.system.body_count:
            text = 'Pioneer:'
        else:
            text = 'Pioneer: Scanning'
        if system_status.honked:
            text += ' (H)'
        if system_status.fully_scanned:
            if this.system_was_scanned:
                text += ' (S)'
            else:
                text += ' (S+)'
            if this.planet_count > 0 and this.planet_count == this.map_count:
                if this.system_was_mapped:
                    text += ' (M)'
                else:
                    text += ' (M+)'
        text += '\n'

        if valuable_body_names:
            text += 'Valuable Bodies (> {}):'.format(this.formatter.format_credits(this.min_value.get())) + '\n'
            text += '\n'.join([format_body(b) for b in valuable_body_names])
        if valuable_body_names and exobio_body_names and this.show_biological.get():
            text += '\n'
        if exobio_body_names and this.show_biological.get():
            text += 'Biological Signals (Unmapped):\n'
            while True:
                exo_list = exobio_body_names[:5]
                exobio_body_names = exobio_body_names[5:]
                text += ' ⬦ '.join([b for b in exo_list])
                if len(exobio_body_names) == 0:
                    break
                else:
                    text += '\n'

        if text[-1] != '\n':
            text += '\n'

        text += 'B#: {} NB#: {}'.format(this.system.body_count, this.system.non_body_count)
        this.label['text'] = text
    else:
        this.label['text'] = 'Pioneer: Nothing Scanned'

    total_value, min_total_value, max_value, min_max_value = calc_system_value()
    if total_value != min_total_value:
        this.total_label['text'] = 'Estimated System Value: {} to {}'.format(
            this.formatter.format_credits(min_total_value), this.formatter.format_credits(total_value))
        if this.show_carrier_values.get():
            this.total_label['text'] += '\nCarrier Value: Up to {} (+{} -> carrier)'.format(
                this.formatter.format_credits(int(total_value*.75)),
                this.formatter.format_credits(int(total_value*.125)))
        this.total_label['text'] += '\nMaximum System Value: {} to {}'.format(
            this.formatter.format_credits(min_max_value), this.formatter.format_credits(max_value))
    elif total_value != max_value:
        this.total_label['text'] = 'Estimated System Value: {}'.format(
            this.formatter.format_credits(total_value) if total_value > 0 else 'N/A')
        if this.show_carrier_values.get() and total_value > 0:
            this.total_label['text'] += '\nCarrier Value: {} (+{} -> carrier)'.format(
                this.formatter.format_credits(int(total_value*.75)),
                this.formatter.format_credits(int(total_value*.125)))
        this.total_label['text'] += '\nMaximum System Value: {}'.format(
            this.formatter.format_credits(max_value) if max_value > 0 else 'N/A')
    else:
        this.total_label['text'] = 'Estimated System Value (Max): {}'.format(
            this.formatter.format_credits(total_value) if total_value > 0 else 'N/A')
        if this.show_carrier_values.get() and total_value > 0:
            this.total_label['text'] += '\nCarrier Value: {} (+{} -> carrier)'.format(
                this.formatter.format_credits(int(total_value*.75)),
                this.formatter.format_credits(int(total_value*.125)))

    if this.use_overlay.get() and this.overlay.available():
        if this.label['text']:
            overlay_text = this.label['text'] + "\n \n" + this.total_label['text']
            this.overlay.display("pioneer_text", overlay_text,
                            x=this.overlay_anchor_x.get(), y=this.overlay_anchor_y.get(),
                            color=this.overlay_color.get())
        else:
            this.overlay.display("pioneer_text", "Pioneer: Waiting for Data",
                            x=this.overlay_anchor_x.get(), y=this.overlay_anchor_y.get(),
                            color=this.overlay_color.get())

    if this.show_details.get():
        this.scroll_canvas.grid()
        this.scrollbar.grid()
    else:
        this.scroll_canvas.grid_remove()
        this.scrollbar.grid_remove()


def bind_mousewheel(event: tk.Event) -> None:
    if sys.platform in ('linux', 'cygwin', 'msys'):
        this.scroll_canvas.bind_all('<Button-4>', on_mousewheel)
        this.scroll_canvas.bind_all('<Button-5>', on_mousewheel)
    else:
        this.scroll_canvas.bind_all('<MouseWheel>', on_mousewheel)


def unbind_mousewheel(event: tk.Event) -> None:
    if sys.platform in ('linux', 'cygwin', 'msys'):
        this.scroll_canvas.unbind_all('<Button-4>')
        this.scroll_canvas.unbind_all('<Button-5>')
    else:
        this.scroll_canvas.unbind_all('<MouseWheel>')


def on_mousewheel(event: tk.Event) -> None:
    shift = (event.state & 0x1) != 0
    scroll = 0
    if event.num == 4 or event.delta == 120:
        scroll = -1
    if event.num == 5 or event.delta == -120:
        scroll = 1
    if shift:
        this.scroll_canvas.xview_scroll(scroll, 'units')
    else:
        this.scroll_canvas.yview_scroll(scroll, 'units')
