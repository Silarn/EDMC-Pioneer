# -*- coding: utf-8 -*-
# Pioneer (System Value) plugin for EDMC
# Source: https://github.com/Silarn/EDMC-Pioneer
# Inspired by Economical Cartographics: https://github.com/n-st/EDMC-EconomicalCartographics
# Licensed under the [GNU Public License (GPL)](http://www.gnu.org/licenses/gpl-2.0.html) version 2 or later.
import logging
import os
import re
from datetime import datetime

import requests
import semantic_version
import sys
from traceback import print_exc
from typing import Any, MutableMapping, Mapping

import tkinter as tk
from tkinter import ttk, colorchooser as tkColorChooser, Widget as tkWidget

from ttkHyperlinkLabel import HyperlinkLabel
from sqlalchemy import select, desc, asc
from sqlalchemy.orm import Session

import myNotebook as nb
import plug
from config import config
from theme import theme
from EDMCLogging import get_plugin_logger

import ExploData
from ExploData.explo_data import db
from ExploData.explo_data.db import System, Commander, SystemStatus, Metadata, StarRing, Death, Resurrection, \
    SystemSale, PlanetStatus, StarStatus, Planet, Star
from ExploData.explo_data.RegionMap import findRegion
from ExploData.explo_data.body_data.struct import PlanetData, StarData, load_planets, load_stars, get_main_star, \
    NonBodyData, load_non_bodies
from ExploData.explo_data.journal_parse import register_event_callbacks, parse_journals, register_journal_callbacks
import ExploData.explo_data.edsm_parse
from ExploData.explo_data.edsm_parse import register_edsm_callbacks

import pioneer.const
from pioneer.body_calc import get_body_value, get_star_value, get_starclass_k, get_planetclass_k
from pioneer.data import BodyValueData
from pioneer.globals import pioneer_globals
from pioneer.status_flags import StatusFlags
from pioneer.util import get_star_label, get_body_shorthand
from pioneer.tooltip import Tooltip

efficiency_bonus = 1.25
this = pioneer_globals
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
        if db_version.value.isdigit() and int(db_version.value) != pioneer.const.db_version:
            this.db_mismatch = True

        if not this.db_mismatch:
            register_event_callbacks(
                {'Scan', 'FSSDiscoveryScan', 'FSSAllBodiesFound', 'SAAScanComplete', 'SellExplorationData',
                 'MultiSellExplorationData', 'Died', 'Resurrect'},
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
        this.label = tk.Label(this.frame, text='Pioneer: ExploData Version Mismatch')
        this.label.grid(row=0, sticky=tk.EW)
        this.update_button = HyperlinkLabel(this.frame, text='You May Need to Update',
                                            url='https://github.com/Silarn/EDMC-Pioneer/releases/latest')
        this.update_button.grid(row=1, columnspan=2, sticky=tk.N)
    else:
        parse_config()
        if not len(sorted(plug.PLUGINS, key=lambda item: item.name == 'BioScan')):  # type: list[plug.Plugin]
            register_journal_callbacks(this.frame, 'pioneer', journal_start, journal_update, journal_end)
        register_edsm_callbacks(this.frame,'pioneer', edsm_start, edsm_end)
        this.label = tk.Label(this.frame)
        this.label.grid(row=0, column=0, sticky=tk.N)
        this.view_button = tk.Button(this.frame, text='🔼', command=toggle_view)
        this.view_button.grid(row=0, column=1, sticky=tk.N)
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
        if not len(sorted(plug.PLUGINS, key=lambda item: item.name == 'BioScan')):  # type: list[plug.Plugin]
            this.edsm_button = tk.Label(this.frame, text='Fetch EDSM Data', fg='white', cursor='hand2')
            this.edsm_button.grid(row=3, columnspan=2, sticky=tk.EW)
            this.edsm_button.bind('<Button-1>', lambda e: edsm_fetch())
        this.started = True
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


def plugin_prefs(parent: ttk.Notebook, cmdr: str, is_beta: bool) -> nb.Frame:
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

    title_frame = tk.Frame(frame, background='')
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

    ttk.Separator(frame).grid(row=5, columnspan=3, pady=y_padding * 2, sticky=tk.EW)
    nb.Label(frame, text='Valuable Body Minimum:').grid(row=10, column=0, padx=x_padding, sticky=tk.W)
    vcmd = (frame.register(validate_int))
    nb.EntryMenu(frame, textvariable=this.min_value,
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
    nb.Checkbutton(
        frame,
        text='Show mapped body count',
        variable=this.show_map_counter
    ).grid(row=32, columnspan=3, padx=x_button_padding, sticky=tk.W)
    sell_cutoff_label = nb.Label(frame, text='Sell event cutoff: (?)')
    sell_cutoff_label.grid(row=33, column=0, padx=x_padding, sticky=tk.W)

    nb.EntryMenu(frame, textvariable=this.max_sell_events,
             validate='all', validatecommand=(vcmd, '%P')).grid(row=33, column=1, sticky=tk.W)
    Tooltip(
        sell_cutoff_label,
        text='Number of data sales before scanned systems are no longer considered unsold.\n\n' +
        'This serves as a backup if journal events are incomplete, which can cause systems to remain flagged as unsold.\n\n' +
        'The plugin will only consider system scans after that date. Ship loss will still apply.',
        waittime=1000
    )

    # Overlay settings
    ttk.Separator(frame).grid(row=35, columnspan=3, pady=y_padding * 2, sticky=tk.EW)

    nb.Label(frame,
             text='EDMC Overlay Integration',
             justify=tk.LEFT) \
        .grid(row=40, column=0, padx=x_padding, sticky=tk.NW)
    nb.Checkbutton(
        frame,
        text='Enable overlay',
        variable=this.use_overlay
    ).grid(row=41, column=0, padx=x_button_padding, pady=0, sticky=tk.W)
    color_button = tk.Button(
        frame,
        text='Text Color',
        foreground=this.overlay_color.get(),
        background='grey4',
        command=lambda: color_chooser()
    )
    color_button.grid(row=42, column=0, padx=x_button_padding, pady=y_padding, sticky=tk.W)

    anchor_frame = tk.Frame(frame, background='')
    anchor_frame.grid(row=41, column=1, sticky=tk.NSEW)
    anchor_frame.columnconfigure(4, weight=1)

    nb.Label(anchor_frame, text='Display Anchor:') \
        .grid(row=0, column=0, sticky=tk.W)
    nb.Label(anchor_frame, text='X') \
        .grid(row=0, column=1, sticky=tk.W)
    nb.EntryMenu(
        anchor_frame, text=this.overlay_anchor_x.get(), textvariable=this.overlay_anchor_x,
        width=8, validate='all', validatecommand=(vcmd, '%P')
    ).grid(row=0, column=2, sticky=tk.W)
    nb.Label(anchor_frame, text='Y') \
        .grid(row=0, column=3, sticky=tk.W)
    nb.EntryMenu(
        anchor_frame, text=this.overlay_anchor_y.get(), textvariable=this.overlay_anchor_y,
        width=8, validate='all', validatecommand=(vcmd, '%P')
    ).grid(row=0, column=4, sticky=tk.W)

    ttk.Separator(frame, orient=tk.HORIZONTAL).grid(row=55, columnspan=3, pady=y_padding * 2, sticky=tk.EW)

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
    config.set('pioneer_map_counter', this.show_map_counter.get())
    config.set('pioneer_max_sell_events', this.max_sell_events.get())
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
    this.show_map_counter = tk.BooleanVar(value=config.get_bool(key='pioneer_map_counter', default=False))
    this.max_sell_events = tk.IntVar(value=config.get_int(key='pioneer_max_sell_events', default=5))
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


def edsm_fetch() -> None:
    ExploData.explo_data.edsm_parse.edsm_fetch(this.system.name)


def edsm_start(event: tk.Event) -> None:
    this.fetched_edsm = True
    update_display()


def edsm_end(event: tk.Event) -> None:
    reload_system_data()
    update_display()


def calc_system_value() -> tuple[int, int, int, int]:
    global efficiency_bonus

    this.overlay_local_text = ''
    this.body_sale_status = {}
    have_belts = this.belt_count == this.belts_found
    bodies_sold = 0
    bodies_lost = 0
    if not this.main_star_name and not len(this.bodies):
        this.values_label['text'] = 'No scans detected.\nHonk or check nav beacon data.'
        return 0, 0, 0, 0
    honk_sum, min_honk_sum = 0, 0
    bodies_text = ''
    sold: list[SystemSale] = this.sql_session.scalars(select(SystemSale).where(SystemSale.commander_id == this.commander.id)
                                                      .where(SystemSale.systems.like(f'%{this.system.name}%'))).all()
    main_star = get_main_star(this.system, this.sql_session)
    main_star_lost = False
    main_star_sold = False
    if main_star:
        main_star_status = this.sql_session.scalar(select(StarStatus).where(StarStatus.commander_id == this.commander.id)
                                                   .where(StarStatus.star_id == main_star.id))
        if main_star_status and main_star_status.scanned_at:
            death = this.sql_session.scalar(select(Death).where(Death.commander_id == this.commander.id)
                                             .where(Death.in_ship).where(Death.died_at > main_star_status.scanned_at)
                                             .order_by(asc(Death.died_at)))
            resurrection = this.sql_session.scalar(select(Resurrection).where(Resurrection.commander_id == this.commander.id)
                                                   .where(Resurrection.type.not_in(['escape', 'rejoin', 'handin', 'recover']))
                                                   .where(Resurrection.resurrected_at > main_star_status.scanned_at)
                                                   .order_by(asc(Resurrection.resurrected_at)))
            lost_at = None
            if death and resurrection:
                lost_at = death.died_at if death.died_at < resurrection.resurrected_at else resurrection.resurrected_at
            elif death:
                lost_at = death.died_at
            elif resurrection:
                lost_at = resurrection.resurrected_at
            for sale in sold:
                if lost_at:
                    if main_star_status.scanned_at < sale.sold_at < lost_at:
                        main_star_sold = True
                        bodies_sold += 1
                        break
                if main_star_status.scanned_at < sale.sold_at:
                    main_star_sold = True
                    bodies_sold += 1
                    break
            if lost_at and not main_star_sold:
                main_star_lost = True
                bodies_lost += 1
    max_value_sum = this.main_star_value if not main_star_lost else 0
    min_max_value_sum = this.main_star_value if not main_star_lost else 0
    value_sum = this.main_star_value if not main_star_lost else 0
    min_value_sum = this.main_star_value if not main_star_lost else 0
    for body_name, body_data in sorted(this.bodies.items(), key=lambda item: item[1].get_id()):
        is_range = this.body_values[body_name].get_mapped_values()[1] != \
                   this.body_values[body_name].get_mapped_values()[0]
        scanned_at = body_data.scanned_at(this.commander.id)
        lost = False
        body_sold = False
        if scanned_at:
            death = this.sql_session.scalar(select(Death).where(Death.commander_id == this.commander.id)
                                             .where(Death.in_ship).where(Death.died_at > scanned_at)
                                             .order_by(asc(Death.died_at)))
            resurrection = this.sql_session.scalar(select(Resurrection).where(Resurrection.commander_id == this.commander.id)
                                                   .where(Resurrection.type.not_in(['escape', 'rejoin', 'handin', 'recover']))
                                                   .where(Resurrection.resurrected_at > scanned_at)
                                                   .order_by(asc(Resurrection.resurrected_at)))
            lost_at = None
            if death and resurrection:
                lost_at = death.died_at if death.died_at < resurrection.resurrected_at else resurrection.resurrected_at
            elif death:
                lost_at = death.died_at
            elif resurrection:
                lost_at = resurrection.resurrected_at
            for sale in sold:
                if lost_at:
                    if scanned_at < sale.sold_at < lost_at:
                        body_sold = True
                        bodies_sold += 1
                        break
                if scanned_at < sale.sold_at:
                    body_sold = True
                    bodies_sold += 1
                    break
            if lost_at and not body_sold:
                lost = True
                bodies_lost += 1

        body_text = '{} - {}{}{}{}{}{}{}{}{}:'.format(
            body_name,
            body_data.get_type() if type(body_data) is PlanetData else
            get_star_label(body_data.get_type(),
                           body_data.get_subclass(),
                           body_data.get_luminosity(),
                           this.show_descriptors.get()),
            ' \N{DECIDUOUS TREE}' if type(body_data) is PlanetData and body_data.is_terraformable() else '',
            ' \N{SUNSET OVER BUILDINGS}' if type(body_data) is PlanetData and not body_data.was_discovered(this.commander.id)
                              and body_data.was_mapped(this.commander.id) else '',
            ' \N{COMPASS}' if body_data.get_scan_state(this.commander.id) < 2 else '',
            ' \N{COLLISION SYMBOL}' if lost else '',
            ' \N{HEAVY DOLLAR SIGN}' if body_sold else '',
            ' \N{WHITE EXCLAMATION MARK ORNAMENT}\N{FOOT}' if type(body_data) is PlanetData and body_data.was_footfalled(this.commander.id) is True else
                ' \N{FOOT}' if type(body_data) is PlanetData and  body_data.footfall(this.commander.id) else '',
            ' \N{WHITE EXCLAMATION MARK ORNAMENT}\N{LEFT-POINTING MAGNIFYING GLASS}' if body_data.was_discovered(this.commander.id) else '',
            ' \N{WHITE EXCLAMATION MARK ORNAMENT}\N{WORLD MAP}\N{VARIATION SELECTOR-16}' if type(body_data) is PlanetData and body_data.was_mapped(this.commander.id) else ''
        ) + '\n'
        if type(body_data) is PlanetData and body_data.is_mapped(this.commander.id):
            efficiency = efficiency_bonus if body_data.was_efficient(this.commander.id) else 1
            mapped_at = body_data.mapped_at(this.commander.id)
            map_lost = False
            map_sold = False
            death = this.sql_session.scalar(select(Death).where(Death.commander_id == this.commander.id)
                                             .where(Death.in_ship).where(Death.died_at > mapped_at)
                                             .order_by(asc(Death.died_at)))
            resurrection = this.sql_session.scalar(select(Resurrection).where(Resurrection.commander_id == this.commander.id)
                                                   .where(Resurrection.type.not_in(['escape', 'rejoin', 'handin', 'recover']))
                                                   .where(Resurrection.resurrected_at > mapped_at)
                                                   .order_by(asc(Resurrection.resurrected_at)))
            map_lost_at = None
            if death and resurrection:
                map_lost_at = death.died_at if death.died_at < resurrection.resurrected_at else resurrection.resurrected_at
            elif death:
                map_lost_at = death.died_at
            elif resurrection:
                map_lost_at = resurrection.resurrected_at
            for sale in sold:
                if map_lost_at:
                    if mapped_at < sale.sold_at < map_lost_at:
                        map_sold = True
                        # bodies_sold += 1
                        break
                if mapped_at < sale.sold_at:
                    map_sold = True
                    # bodies_sold += 1
                    break
            if map_lost_at and not map_sold:
                map_lost = True
                # bodies_lost += 1
            this.body_sale_status[this.bodies[body_name].get_id()] = (sold, lost, map_sold, map_lost)
            if map_lost:
                min_value = this.body_values[body_name].get_base_values()[1] \
                    if (body_data.get_scan_state(this.commander.id) > 1 and
                        body_data.is_discovered(this.commander.id)) else 0
                max_value = this.body_values[body_name].get_base_values()[0] \
                    if (body_data.get_scan_state(this.commander.id) > 1 and
                        body_data.is_discovered(this.commander.id)) else 0
                min_mapped_value = int(this.body_values[body_name].get_mapped_values()[1] * efficiency_bonus)
                max_mapped_value = int(this.body_values[body_name].get_mapped_values()[0] * efficiency_bonus)
                val_text = '{} - {}'.format(
                    this.formatter.format_credits(min_value), this.formatter.format_credits(max_value)
                ) if is_range else '{}'.format(this.formatter.format_credits(max_value))
                lost_val_text = '{} - {}'.format(
                    this.formatter.format_credits(min_mapped_value-min_value),
                    this.formatter.format_credits(max_mapped_value-max_value)
                ) if is_range else '{}'.format(
                    this.formatter.format_credits(max_mapped_value-max_value)
                )
                max_val_text = '{} - {}'.format(
                    this.formatter.format_credits(min_mapped_value),
                    this.formatter.format_credits(max_mapped_value)
                ) if is_range else '{}'.format(
                    this.formatter.format_credits(max_mapped_value)
                )
                body_text += 'Current Value: {}{}\n'.format(val_text, ' (Lost)' if lost else '')
                body_text += '  Mapped{}\N{COLLISION SYMBOL}\n'.format(
                    ' (Efficient)' if body_data.was_efficient(this.commander.id) else ''
                )
                body_text += '  Lost: {}\n'.format(lost_val_text)
                if this.show_carrier_values.get() and not lost:
                    body_text += 'Carrier Value: {}{} ({} -> carrier)\n'.format(
                        'Up to ' if is_range else '',
                        this.formatter.format_credits(int(max_value * .75)),
                        this.formatter.format_credits(int(max_value * .125))
                    )
                body_text += 'Max Value: {}\n'.format(max_val_text)
                if not lost:
                    max_value_sum += max_mapped_value
                    min_max_value_sum += min_mapped_value
                    value_sum += max_value
                    min_value_sum += min_value
            else:
                val_text = '{} - {}'.format(
                    this.formatter.format_credits(this.body_values[body_name].get_mapped_values()[1] * efficiency),
                    this.formatter.format_credits(this.body_values[body_name].get_mapped_values()[0] * efficiency)) \
                    if is_range else \
                    '{}'.format(this.formatter.format_credits(
                        this.body_values[body_name].get_mapped_values()[0] * efficiency
                    ))
                body_text += 'Current Value (Max): {}{}\n'.format(val_text, ' (Lost)' if lost else '')
                body_text += '  Mapped{}{}\n'.format(
                    ' (Efficient)' if body_data.was_efficient(this.commander.id) else '',
                    ' \N{HEAVY DOLLAR SIGN}' if body_sold else ''
                )
                if this.show_carrier_values.get() and not lost:
                    body_text += 'Carrier Value: {}{} ({} -> carrier)\n'.format(
                        'Up to ' if is_range else '',
                        this.formatter.format_credits(
                            int(this.body_values[body_name].get_mapped_values()[0] * efficiency * .75)),
                        this.formatter.format_credits(
                            int(this.body_values[body_name].get_mapped_values()[0] * efficiency * .125))
                    )
                max_value_sum += this.body_values[body_name].get_mapped_values()[0] * efficiency
                min_max_value_sum += this.body_values[body_name].get_mapped_values()[1] * efficiency
                value_sum += this.body_values[body_name].get_mapped_values()[0] * efficiency
                min_value_sum += this.body_values[body_name].get_mapped_values()[1] * efficiency
        elif type(body_data) is PlanetData:
            this.body_sale_status[this.bodies[body_name].get_id()] = (sold, lost, False, False)
            min_value = this.body_values[body_name].get_base_values()[1] \
                if (body_data.get_scan_state(this.commander.id) > 1 and
                    body_data.is_discovered(this.commander.id)) else 0
            max_value = this.body_values[body_name].get_base_values()[0] \
                if (body_data.get_scan_state(this.commander.id) > 1 and
                    body_data.is_discovered(this.commander.id)) else 0
            min_mapped_value = int(this.body_values[body_name].get_mapped_values()[1] * efficiency_bonus)
            max_mapped_value = int(this.body_values[body_name].get_mapped_values()[0] * efficiency_bonus)
            val_text = '{} - {}'.format(
                this.formatter.format_credits(min_value), this.formatter.format_credits(max_value)
            ) if is_range else '{}'.format(this.formatter.format_credits(max_value))
            max_val_text = '{} - {}'.format(
                this.formatter.format_credits(min_mapped_value),
                this.formatter.format_credits(max_mapped_value)
            ) if is_range else '{}'.format(
                this.formatter.format_credits(max_mapped_value)
            )
            body_text += 'Current Value: {}{}\n'.format(val_text, ' (Lost)' if lost else '')
            if this.show_carrier_values.get() and not lost:
                body_text += 'Carrier Value: {}{} ({} -> carrier)\n'.format(
                    'Up to ' if is_range else '',
                    this.formatter.format_credits(int(max_value * .75)),
                    this.formatter.format_credits(int(max_value * .125))
                )
            body_text += 'Max Value: {}\n'.format(max_val_text)
            if not lost:
                max_value_sum += max_mapped_value
                min_max_value_sum += min_mapped_value
                value_sum += max_value
                min_value_sum += min_value
        else:
            this.body_sale_status[this.bodies[body_name].get_id()] = (sold, lost, False, False)
            min_value = this.body_values[body_name].get_base_values()[1] \
                if (body_data.get_scan_state(this.commander.id) > 1
                    and body_data.is_discovered(this.commander.id)) else 0
            max_value = this.body_values[body_name].get_base_values()[0] \
                if (body_data.get_scan_state(this.commander.id) > 1
                    and body_data.is_discovered(this.commander.id)) else 0
            val_text = '{} - {}'.format(
                this.formatter.format_credits(min_value),
                this.formatter.format_credits(max_value)
            ) if is_range else '{}'.format(
                this.formatter.format_credits(max_value)
            )
            body_text += 'Current Value (Max): {}{}\n'.format(val_text, ' (Lost)' if lost else '')
            if this.show_carrier_values.get() and not lost:
                body_text += 'Carrier Value: {}{} ({} -> carrier)\n'.format(
                    'Up to ' if is_range else '',
                    this.formatter.format_credits(int(max_value * .75)),
                    this.formatter.format_credits(int(max_value * .125))
                )
            if not lost:
                max_value_sum += max_value
                min_max_value_sum += min_value
                value_sum += max_value
                min_value_sum += min_value
        min_honk_value = this.body_values[body_name].get_honk_values()[1] \
            if (body_data.get_scan_state(this.commander.id) > 1
                and body_data.is_discovered(this.commander.id)) else 0
        max_honk_value = this.body_values[body_name].get_honk_values()[0] \
            if (body_data.get_scan_state(this.commander.id) > 1
                and body_data.is_discovered(this.commander.id)) else 0
        if get_system_status().honked:
            if max_honk_value != min_honk_value:
                body_text += 'Honk Value: {} - {}'.format(
                    this.formatter.format_credits(min_honk_value),
                    this.formatter.format_credits(max_honk_value)) + '\n'
            else:
                body_text += 'Honk Value: {}'.format(
                    this.formatter.format_credits(max_honk_value)
                ) + '\n'
            if not lost:
                value_sum += max_honk_value if this.main_star_value else 0
                min_value_sum += min_honk_value if this.main_star_value else 0
                honk_sum += max_honk_value
                min_honk_sum += min_honk_value
        if not lost:
            max_value_sum += max_honk_value if this.main_star_value else 0
            min_max_value_sum += min_honk_value if this.main_star_value else 0
        if body_data.get_name() == this.current_body_name:
            this.overlay_local_text += '\n' + body_text
        bodies_text += body_text
        bodies_text += '------------------' + '\n'
    if this.main_star_name:
        star_text = '{}{}{}:\n   {}\n   {} + {} = {}\n'.format(
            this.main_star_name,
            '\N{COLLISION SYMBOL}' if main_star_lost else '',
            '\N{HEAVY DOLLAR SIGN}' if main_star_sold else '',
            this.main_star_type,
            this.formatter.format_credits(this.main_star_value),
            this.formatter.format_credits(honk_sum) if honk_sum == min_honk_sum else '{} to {}{}'.format(
                this.formatter.format_credits(min_honk_sum),
                this.formatter.format_credits(honk_sum),
                ' (Lost)' if main_star_lost else ''
            ),
            (this.formatter.format_credits(
                this.main_star_value + honk_sum)) if honk_sum == min_honk_sum else '{} to {}'.format(
                this.formatter.format_credits(this.main_star_value + min_honk_sum),
                this.formatter.format_credits(this.main_star_value + honk_sum)
            ))
        if this.show_carrier_values.get() and not main_star_lost:
            is_range = honk_sum != min_honk_sum
            star_text += '   Carrier: {}{} ({} -> carrier)\n'.format(
                'Up to ' if is_range else '',
                this.formatter.format_credits(int((this.main_star_value + honk_sum) * .75)),
                this.formatter.format_credits(int((this.main_star_value + honk_sum) * .125))
            )
        this.values_label['text'] = star_text
        this.overlay_local_text = star_text + this.overlay_local_text
    else:
        this.values_label['text'] = 'No main star info\nCheck for nav beacon data\n'
    this.values_label['text'] += '------------------' + '\n'
    this.values_label['text'] += bodies_text
    status = get_system_status()
    if not this.system_was_scanned and not this.is_nav_beacon and not this.system_has_undiscovered and not bodies_lost:
        total_bodies = this.non_body_count + this.system.body_count
        if status.fully_scanned and have_belts:
            this.values_label['text'] += 'Fully Scanned Bonus: {}'.format(
                this.formatter.format_credits(total_bodies * 1000)
            ) + '\n'
            value_sum += total_bodies * 1000
            min_value_sum += total_bodies * 1000
        max_value_sum += total_bodies * 1000
        min_max_value_sum += total_bodies * 1000
    if not this.system_was_mapped and this.planet_count > 0 and not bodies_lost:
        if status.fully_scanned and this.planet_count == this.map_count:
            this.values_label['text'] += 'Fully Mapped Bonus: {}'.format(
                this.formatter.format_credits(this.planet_count * 10000)) + '\n'
            value_sum += this.planet_count * 10000
            min_value_sum += this.planet_count * 10000
        max_value_sum += this.planet_count * 10000
        min_max_value_sum += this.planet_count * 10000
    this.scroll_canvas.configure(width=100)
    tkWidget.nametowidget(this.frame, name=this.frame.winfo_parent()).update()
    label_width = this.values_label.winfo_width()
    full_width = this.label.winfo_width() - this.scrollbar.winfo_width()
    final_width = label_width if label_width > full_width else full_width
    this.scroll_canvas.configure(width=final_width)
    return value_sum, min_value_sum, max_value_sum, min_max_value_sum


def get_system_value(system: System) -> tuple[int, int]:
    global efficiency_bonus

    system_status = this.sql_session.scalar(select(SystemStatus).where(SystemStatus.system_id == system.id)
                                            .where(SystemStatus.commander_id == this.commander.id))

    if not system_status:
        return 0, 0

    have_belts = False
    for star in system.stars:
        for ring in star.rings:
            if ring.name.endswith('Belt'):
                have_belts = True
    value_sum = 0
    min_value_sum = 0
    honk_sum, min_honk_sum = 0, 0
    main_star_scanned = False
    bodies = system.stars + system.planets

    system_was_scanned = False
    system_was_mapped = False
    map_count = 0
    body_data: PlanetData | StarData
    for body in bodies:
        if isinstance(body, Planet):
            body_data = PlanetData.from_journal(system, body.name, body.body_id, this.sql_session)
        else:
            body_data = StarData.from_journal(system, body.name, body.body_id, this.sql_session)

        if body_data.was_discovered(this.commander.id):
            system_was_scanned = True

        body_values = calculate_body_values(body_data)
        if type(body_data) is PlanetData and body_data.is_mapped(this.commander.id):
            if body_data.was_mapped(this.commander.id):
                system_was_mapped = True
            map_count += 1
            efficiency = efficiency_bonus if body_data.was_efficient(this.commander.id) else 1
            value_sum += body_values.get_mapped_values()[0] * efficiency
            min_value_sum += body_values.get_mapped_values()[1] * efficiency
        elif type(body_data) is PlanetData:
            if body_data.was_mapped(this.commander.id):
                system_was_mapped = True
            min_value = body_values.get_base_values()[1] \
                if (body_data.get_scan_state(this.commander.id) > 1 and
                    body_data.is_discovered(this.commander.id)) else 0
            max_value = body_values.get_base_values()[0] \
                if (body_data.get_scan_state(this.commander.id) > 1 and
                    body_data.is_discovered(this.commander.id)) else 0
            value_sum += max_value
            min_value_sum += min_value
        else:
            if body_data.get_distance() == 0 and body_data.get_scan_state(this.commander.id) > 1:
                main_star_scanned = True
            min_value = body_values.get_base_values()[1] \
                if (body_data.get_scan_state(this.commander.id) > 1
                    and body_data.is_discovered(this.commander.id)) else 0
            max_value = body_values.get_base_values()[0] \
                if (body_data.get_scan_state(this.commander.id) > 1
                    and body_data.is_discovered(this.commander.id)) else 0
            value_sum += max_value
            min_value_sum += min_value
        min_honk_value = body_values.get_honk_values()[1] \
            if (body_data.get_scan_state(this.commander.id) > 1
                and body_data.is_discovered(this.commander.id)) else 0
        max_honk_value = body_values.get_honk_values()[0] \
            if (body_data.get_scan_state(this.commander.id) > 1
                and body_data.is_discovered(this.commander.id)) else 0
        if system_status.honked:
            value_sum += max_honk_value if main_star_scanned else 0
            min_value_sum += min_honk_value if main_star_scanned else 0
            honk_sum += max_honk_value
            min_honk_sum += min_honk_value

    if not system_was_scanned:
        total_bodies = len(system.non_bodies) + system.body_count
        if system_status.fully_scanned and have_belts:
            value_sum += total_bodies * 1000
            min_value_sum += total_bodies * 1000
    if not system_was_mapped and len(system.planets) > 0:
        if system_status.fully_scanned and len(system.planets) == map_count:
            value_sum += len(system.planets) * 10000
            min_value_sum += len(system.planets) * 10000
    return value_sum, min_value_sum


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
    this.body_sale_status = {}


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

    if cmdr and (not this.commander or this.commander.name != cmdr):
        commander = this.sql_session.scalar(select(Commander).where(Commander.name == cmdr))
        if not commander:
            commander = Commander(name=cmdr)
            this.sql_session.add(this.commander)
            this.sql_session.commit()
        this.commander = commander
        this.recalculate_unsold = True
        this.unsold_systems = {}
        reset()

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
        reload_system_data()

    if not this.system or not this.commander:
        return ''

    match entry['event']:
        case 'StartJump':
            if entry['JumpType'] == 'Hyperspace':
                reset()
                update_display()
        case 'Disembark':
            if entry.get('OnPlanet', False):
                body_short_name = get_body_name(entry['BodyName'])
                if body_short_name in this.bodies:
                    this.bodies[body_short_name].refresh()
                else:
                    this.bodies[body_short_name] = PlanetData.from_journal(this.system, body_short_name,
                                                                           entry['BodyID'], this.sql_session)
                update_display()

    this.sql_session.commit()

    if system_changed:
        this.scroll_canvas.yview_moveto(0.0)

    if this.system:
        calc_counts()
        update_display()

    return ''  # No error


def reload_system_data() -> None:
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
        process_belts()
    process_discovery()


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
            process_belts()
            process_discovery()
            if body and body.get_scan_state(this.commander.id) > 1:
                this.unsold_systems[this.system.id] = True
            update_display()

        case 'FSSDiscoveryScan':
            if entry['Progress'] == 1.0 and not get_system_status().fully_scanned:
                get_system_status().fully_scanned = True
                this.sql_session.commit()
            update_display()

        case 'FSSAllBodiesFound':
            process_belts()
            update_display()

        case 'SAAScanComplete':
            body_short_name = get_body_name(entry['BodyName'])
            if body_short_name.endswith('Ring') or body_short_name.find('Belt Cluster') != -1:
                process_belts()
                return
            if body_short_name in this.bodies:
                this.bodies[body_short_name].refresh()
            else:
                this.bodies[body_short_name] = PlanetData.from_journal(this.system, body_short_name,
                                                                       entry['BodyID'], this.sql_session)
            update_display()

        case 'SellExplorationData':
            systems: list[str] = entry['Systems']
            for system_name in systems:
                system = this.sql_session.scalar(select(System).where(System.name == system_name))
                this.unsold_systems[system.id] = (0, 0)
            update_display()

        case 'MultiSellExplorationData':
            for system_data in entry['Discovered']:
                system = this.sql_session.scalar(select(System).where(System.name == system_data['SystemName']))
                this.unsold_systems[system.id] = (0, 0)
            update_display()

        case 'Died' | 'Resurrect':
            this.recalculate_unsold = True
            update_display()

    calc_counts()


def dashboard_entry(cmdr: str, is_beta: bool, entry: dict[str, Any]) -> str:
    status = StatusFlags(entry['Flags'])
    update = False

    body_name = get_body_name(entry.get('BodyName', ''))
    body_name = body_name if body_name else get_body_name(entry.get('Destination', {'Name': ''})['Name'])
    if body_name != this.current_body_name:
        this.current_body_name = body_name
        update = True

    if this.analysis_mode != (StatusFlags.IS_ANALYSIS_MODE in status):
        this.analysis_mode = (StatusFlags.IS_ANALYSIS_MODE in status)
        update = True

    fsd_jump = StatusFlags.FSD_JUMP_IN_PROGRESS in status
    if fsd_jump != this.fsd_jump:
        if this.system and fsd_jump:
            this.fsd_jump = True
        else:
            this.fsd_jump = False
        update = True

    in_flight = False
    if StatusFlags.IN_SHIP in status or StatusFlags.IN_FIGHTER in status:
        if (StatusFlags.DOCKED in status) or (StatusFlags.LANDED in status):
            in_flight = False
        else:
            in_flight = True

    if in_flight != this.in_flight:
        this.in_flight = in_flight
        update = True

    gui_focus = int(entry.get('GuiFocus', 0))
    if gui_focus != this.gui_focus and ((gui_focus in [0, 2, 9, 10]) != (this.gui_focus in [0, 2, 9, 10])):
        update = True
    this.gui_focus = gui_focus

    if update:
        update_display()

    return ''


def calc_counts() -> None:
    this.planet_count = 0
    this.map_count = 0
    this.non_body_count = len(this.non_bodies)
    for body in this.bodies.values():
        if type(body) is PlanetData:
            this.planet_count += 1
            if body.is_mapped(this.commander.id) and (body.get_id() in this.body_sale_status
                                                      and not this.body_sale_status[body.get_id()][3]):
                this.map_count += 1

    if len(this.bodies) > this.system.body_count and not get_system_status().honked:
        this.system.body_count = len(this.bodies)
        this.sql_session.commit()


def process_body_values(body: PlanetData | StarData | None) -> None:
    if not body:
        return

    undiscovered = not body.is_discovered(this.commander.id) or body.get_scan_state(this.commander.id) < 2
    unscanned = body.get_scan_state(this.commander.id) == 0
    if type(body) is StarData:
        if body.get_type() == 'SupermassiveBlackHole':
            value = 261790
            honk_value = 0
        else:
            k = get_starclass_k(body.get_type())
            value, honk_value = get_star_value(
                k, body.get_mass(),
                not body.was_discovered(this.commander.id) if not unscanned else False
            )
        if body.get_distance() == 0.0:
            this.main_star_value = value if not undiscovered else 0
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
        odyssey_bonus = False if not body.was_discovered(this.commander.id) and body.was_mapped(this.commander.id) \
            else odyssey_bonus
        if body.get_name() not in this.body_values or this.body_values[body.get_name()].get_base_values()[0] == 0:
            this.system_was_scanned = True if (body.was_discovered(this.commander.id) or
                                               unscanned) else this.system_was_scanned
            this.system_was_mapped = True if (body.was_mapped(this.commander.id) or
                                              unscanned) else this.system_was_mapped

            k, kt, tm = get_planetclass_k(body.get_type(), body.is_terraformable())
            value, mapped_value, honk_value, \
                min_value, min_mapped_value, min_honk_value = \
                get_body_value(
                    k, kt, tm, body.get_mass(),
                    not body.was_discovered(this.commander.id) if not unscanned else False,
                    not body.was_mapped(this.commander.id) if not unscanned else False,
                    odyssey_bonus)

            if body.get_name() not in this.body_values:
                body_value = BodyValueData(body.get_name(), body.get_id())
            else:
                body_value = this.body_values[body.get_name()]

            body_value.set_base_values(value, min_value).set_honk_values(honk_value, min_honk_value)
            body_value.set_mapped_values(int(mapped_value), int(min_mapped_value))
            this.body_values[body.get_name()] = body_value

    if body.get_distance() > 0.0:
        this.bodies[body.get_name()] = body


def calculate_body_values(body_data: PlanetData | StarData) -> BodyValueData:
    # undiscovered = not body_data.is_discovered(this.commander.id) or body_data.get_scan_state(this.commander.id) < 2
    unscanned = body_data.get_scan_state(this.commander.id) == 0
    body_value = BodyValueData(body_data.get_name(), body_data.get_id())
    if type(body_data) is StarData:
        if body_data.get_type() == 'SupermassiveBlackHole':
            value = 261790
            honk_value = 0
        else:
            k = get_starclass_k(body_data.get_type())
            value, honk_value = get_star_value(
                k, body_data.get_mass(),
                not body_data.was_discovered(this.commander.id) if not unscanned else False
            )
        body_value.set_base_values(value, value).set_mapped_values(value, value) \
            .set_honk_values(honk_value, honk_value)

    if type(body_data) is PlanetData:
        odyssey_bonus = this.odyssey or this.game_version.major >= 4
        odyssey_bonus = False if not body_data.was_discovered(this.commander.id) and body_data.was_mapped(this.commander.id) \
            else odyssey_bonus
        k, kt, tm = get_planetclass_k(body_data.get_type(), body_data.is_terraformable())
        value, mapped_value, honk_value, \
            min_value, min_mapped_value, min_honk_value = \
            get_body_value(
                k, kt, tm, body_data.get_mass(),
                not body_data.was_discovered(this.commander.id) if not unscanned else False,
                not body_data.was_mapped(this.commander.id) if not unscanned else False,
                odyssey_bonus)

        body_value.set_base_values(value, min_value).set_honk_values(honk_value, min_honk_value)
        body_value.set_mapped_values(int(mapped_value), int(min_mapped_value))

    return body_value


def get_system_status() -> SystemStatus | None:
    if not this.system:
        this.system_status = None
    elif this.system_status and (this.system_status.system_id != this.system.id
                                 or this.system_status.commander_id != this.commander.id):
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


def get_unsold_data() -> str:
    unsold_text = ''
    if this.recalculate_unsold:
        last_death: Death = this.sql_session.scalar(select(Death).where(Death.commander_id == this.commander.id)
                                                    .where(Death.in_ship == True).order_by(desc(Death.died_at)))
        last_resurrect: Resurrection = this.sql_session.scalar(select(Resurrection).where(Resurrection.commander_id == this.commander.id)
                                                               .where(Resurrection.type.not_in(['escape', 'rejoin', 'handin', 'recover']))
                                                               .order_by(desc(Resurrection.resurrected_at)))
        recent_sales: list[SystemSale] = this.sql_session.scalars(
            select(SystemSale).where(SystemSale.commander_id == this.commander.id).order_by(desc(SystemSale.sold_at))
            .limit(this.max_sell_events.get())
        ).all()
        data_cutoff_time = recent_sales[-1].sold_at if len(recent_sales) == this.max_sell_events.get() else datetime.min

        last_data_loss: datetime | None = None
        if last_death or last_resurrect:
            last_death_time: datetime = last_death.died_at if last_death else None
            last_resurrect_time: datetime = last_resurrect.resurrected_at if last_resurrect else None
            last_data_loss = last_death_time if last_death_time > last_resurrect_time else last_resurrect_time
        if last_data_loss:
            if data_cutoff_time > datetime.min:
                data_cutoff_time = last_data_loss if last_data_loss > data_cutoff_time else data_cutoff_time
            else:
                data_cutoff_time = last_data_loss

        logger.debug(f'Cutoff time: {data_cutoff_time}')

        planet_scans: list[PlanetStatus] = this.sql_session.scalars(select(PlanetStatus)
                                                                    .where(PlanetStatus.commander_id == this.commander.id)
                                                                    .where(PlanetStatus.scan_state >= 2)
                                                                    .where(PlanetStatus.scanned_at > data_cutoff_time)).all()

        star_scans: list[StarStatus] = this.sql_session.scalars(select(StarStatus)
                                                                .where(StarStatus.commander_id == this.commander.id)
                                                                .where(StarStatus.scan_state >= 2)
                                                                .where(StarStatus.scanned_at > data_cutoff_time)).all()

        systems: set[int] = set()

        for planet_status in planet_scans:
            planet_data = this.sql_session.scalar(select(Planet).where(Planet.id == planet_status.planet_id))
            if planet_data.system_id not in this.unsold_systems:
                systems.add(planet_data.system_id)

        for star_status in star_scans:
            star_data = this.sql_session.scalar(select(Star).where(Star.id == star_status.star_id))
            if star_data.system_id not in this.unsold_systems:
                systems.add(star_data.system_id)
        if len(systems) > 0:
            for system_id in systems:
                system = this.sql_session.scalar(select(System).where(System.id == system_id))
                data_sales = this.sql_session.scalar(select(SystemSale).where(SystemSale.commander_id == this.commander.id)
                                                     .where(SystemSale.systems.like(f'%{system.name}%')))
                if not data_sales:
                    this.unsold_systems[system_id] = get_system_value(system)
                else:
                    this.unsold_systems[system_id] = (0, 0)
        this.recalculate_unsold = False

    if this.system.id in this.unsold_systems and this.unsold_systems[this.system.id] is True:
        this.unsold_systems[this.system.id] = get_system_value(this.system)

    total_value_sum = 0
    min_total_value_sum = 0

    for system_id, values in this.unsold_systems.items():
        total_value, min_total_value = values
        total_value_sum += total_value
        min_total_value_sum += min_total_value

    if total_value_sum > 0:
        if total_value_sum != min_total_value_sum:
            unsold_text = 'Unsold System Value: {} to {}'.format(
                this.formatter.format_credits(min_total_value_sum), this.formatter.format_credits(total_value_sum))
            if this.show_carrier_values.get():
                unsold_text += '\nCarrier Value: Up to {} (+{} -> carrier)'.format(
                    this.formatter.format_credits(int(total_value_sum * .75)),
                    this.formatter.format_credits(int(total_value_sum * .125)))
        else:
            unsold_text = 'Unsold System Value: {}'.format(
                this.formatter.format_credits(total_value_sum) if total_value_sum > 0 else 'N/A')
            if this.show_carrier_values.get() and total_value_sum > 0:
                unsold_text += '\nCarrier Value: {} (+{} -> carrier)'.format(
                    this.formatter.format_credits(int(total_value_sum * .75)),
                    this.formatter.format_credits(int(total_value_sum * .125)))

    return unsold_text


def process_belts() -> None:
    belt_count = 0
    belts_found = 0
    for _, star in filter(lambda item: type(item[1]) is StarData, this.bodies.items()):
        rings: list[StarRing] = star.get_rings()
        for ring in rings:
            if ring.name.endswith('Belt'):
                belt_count += 1
                for _, non_body in this.non_bodies.items():
                    if non_body.get_name().startswith(f'{star.get_name()} {ring.name}'):
                        belts_found += 1
                        break
    main_star = get_main_star(this.system, this.sql_session)
    if main_star:
        name_prefix = '' if main_star.name == this.system.name else main_star.name + ' '
        for ring in main_star.rings:
            if ring.name.endswith('Belt'):
                belt_count += 1
                for _, non_body in this.non_bodies.items():
                    if non_body.get_name().startswith(f'{name_prefix}{ring.name}'):
                        belts_found += 1
                        break
    this.belt_count = belt_count
    this.belts_found = belts_found


def process_discovery() -> None:
    undiscovered = False
    nav = False
    for _, body in this.bodies.items():
        if not body.is_discovered(this.commander.id):
            undiscovered = True
        if body.get_scan_state(this.commander.id) < 2:
            undiscovered = True
            if body.get_scan_state(this.commander.id) == 1:
                nav = True
        if nav and undiscovered:
            break
    this.system_has_undiscovered = undiscovered
    this.is_nav_beacon = nav


def update_display() -> None:
    global efficiency_bonus

    if not this.started:
        return

    if not len(sorted(plug.PLUGINS, key=lambda item: item.name == 'BioScan')):  # type: list[plug.Plugin]
        if this.fetched_edsm or not this.system:
            this.edsm_button.grid_remove()
        else:
            this.edsm_button.grid()
    system_status = get_system_status()
    if not this.display_hidden:
        if not system_status:
            this.label['text'] = 'Pioneer: Awaiting Data'
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

    total_value, min_total_value, max_value, min_max_value = calc_system_value()
    calc_counts()

    valuable_body_names = [
        body_name
        for body_name, body_data
        in sorted(
            this.bodies.items(),
            key=lambda item: item[1].get_distance()
        )
        if type(body_data) is PlanetData
           and this.body_values[body_name].get_mapped_values()[0] * efficiency_bonus >= this.min_value.get()
           and (not body_data.is_mapped(this.commander.id) or
                (body_data.get_id() in this.body_sale_status and this.body_sale_status[body_data.get_id()][3]))
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
        lost = True if (this.bodies[body_name].get_id() in this.body_sale_status and
                        this.body_sale_status[this.bodies[body_name].get_id()][3]) else False
        if body_value >= this.min_value.get():
            return '%s%s (max %s, %s)%s' % \
                (body_name,
                 get_body_shorthand(this.bodies[body_name], this.commander.id),
                 this.formatter.format_credits(body_value, False),
                 this.formatter.format_ls(body_distance),
                 '\N{COLLISION SYMBOL}' if lost else '')
        else:
            return '%s'

    text = ''
    if this.bodies or this.main_star_name:
        all_belts_found = this.belt_count == this.belts_found
        if system_status.fully_scanned and all_belts_found and len(this.bodies) + 1 >= this.system.body_count:
            text = 'Pioneer:'
        else:
            text = 'Pioneer: Scanning'
        if system_status.honked:
            text += ' \N{GLOBE WITH MERIDIANS}'
        if this.is_nav_beacon:
            text += ' \N{COMPASS}'
        if this.system_was_mapped and not this.system_was_scanned:
            text += ' \N{SUNSET OVER BUILDINGS}'
        if system_status.fully_scanned and len(this.bodies) + 1 >= this.system.body_count:
            if all_belts_found and not this.system_has_undiscovered:
                if this.system_was_scanned:
                    text += ' \N{LEFT-POINTING MAGNIFYING GLASS}'
                else:
                    text += ' \N{LEFT-POINTING MAGNIFYING GLASS}\N{GLOWING STAR}'
            if this.planet_count > 0 and this.planet_count == this.map_count:
                if this.system_was_mapped:
                    text += ' \N{WORLD MAP}\N{VARIATION SELECTOR-16}'
                else:
                    text += ' \N{WORLD MAP}\N{VARIATION SELECTOR-16}\N{GLOWING STAR}'
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

        body_count = this.system.body_count if system_status.honked else '?'
        text += f'B#: {len(this.bodies) + 1}/{body_count} NB#: {this.system.non_body_count}'
        if this.belt_count:
            text += f' (Belts: {this.belts_found}/{this.belt_count})'
        if this.show_map_counter.get() and this.planet_count > 0 and this.map_count < this.planet_count:
            text += f' (Mapped: {this.map_count}/{this.planet_count})'
    else:
        text = 'Pioneer: Nothing Scanned'
    if not this.display_hidden:
        this.label['text'] = text

    if total_value != min_total_value:
        this.total_label['text'] = 'Estimated System Value: {} to {}'.format(
            this.formatter.format_credits(min_total_value), this.formatter.format_credits(total_value))
        if this.show_carrier_values.get():
            this.total_label['text'] += '\nCarrier Value: Up to {} (+{} -> carrier)'.format(
                this.formatter.format_credits(int(total_value * .75)),
                this.formatter.format_credits(int(total_value * .125)))
        this.total_label['text'] += '\nMaximum System Value: {} to {}'.format(
            this.formatter.format_credits(min_max_value), this.formatter.format_credits(max_value))
    elif total_value != max_value:
        this.total_label['text'] = 'Estimated System Value: {}'.format(
            this.formatter.format_credits(total_value) if total_value > 0 else 'N/A')
        if this.show_carrier_values.get() and total_value > 0:
            this.total_label['text'] += '\nCarrier Value: {} (+{} -> carrier)'.format(
                this.formatter.format_credits(int(total_value * .75)),
                this.formatter.format_credits(int(total_value * .125)))
        this.total_label['text'] += '\nMaximum System Value: {}'.format(
            this.formatter.format_credits(max_value) if max_value > 0 else 'N/A')
    else:
        this.total_label['text'] = 'Estimated System Value (Max): {}'.format(
            this.formatter.format_credits(total_value) if total_value > 0 else 'N/A')
        if this.show_carrier_values.get() and total_value > 0:
            this.total_label['text'] += '\nCarrier Value: {} (+{} -> carrier)'.format(
                this.formatter.format_credits(int(total_value * .75)),
                this.formatter.format_credits(int(total_value * .125)))

    unsold_text = get_unsold_data()
    if unsold_text:
        this.total_label['text'] += f'\n{unsold_text}'

    if this.use_overlay.get() and this.overlay.available():
        if overlay_should_display():
            if text:
                overlay_text = text + ('\n\n' + this.overlay_local_text if this.overlay_local_text else '') + '\n' + this.total_label['text']
                this.overlay.display("pioneer_text", overlay_text,
                                     x=this.overlay_anchor_x.get(), y=this.overlay_anchor_y.get(),
                                     color=this.overlay_color.get())
            else:
                this.overlay.display("pioneer_text", "Pioneer: Awaiting Data",
                                     x=this.overlay_anchor_x.get(), y=this.overlay_anchor_y.get(),
                                     color=this.overlay_color.get())
        else:
            this.overlay.clear("pioneer_text")

    if not this.display_hidden:
        if this.show_details.get():
            this.scroll_canvas.grid()
            this.scrollbar.grid()
        else:
            this.scroll_canvas.grid_remove()
            this.scrollbar.grid_remove()


def overlay_should_display() -> bool:
    if not this.analysis_mode or not this.in_flight or this.gui_focus not in [0, 2, 9, 10] or this.fsd_jump:
        return False
    return True


def toggle_view():
    this.display_hidden = not this.display_hidden
    if this.display_hidden:
        this.view_button['text'] = '🔽'
    else:
        this.view_button['text'] = '🔼'

    if this.display_hidden:
        this.label['text'] = 'Pioneer (Hidden)'
        this.scroll_canvas.grid_remove()
        this.scrollbar.grid_remove()
        this.total_label.grid_remove()
        this.edsm_button.grid_remove()
    else:
        this.total_label.grid()
    update_display()


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
