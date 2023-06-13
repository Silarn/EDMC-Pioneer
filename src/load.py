# -*- coding: utf-8 -*-
# Pioneer (System Value) plugin for EDMC
# Source: https://github.com/Silarn/EDMC-Pioneer
# Inspired by Economical Cartographics: https://github.com/n-st/EDMC-EconomicalCartographics
# Licensed under the [GNU Public License (GPL)](http://www.gnu.org/licenses/gpl-2.0.html) version 2 or later.

import re
import requests
import semantic_version
import sys
import threading
from traceback import print_exc
from typing import Any, MutableMapping, Mapping, Optional
from urllib.parse import quote

import tkinter as tk
from tkinter import ttk, Widget as tkWidget
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
from pioneer.data import BodyValueData
from pioneer.util import get_star_label, map_edsm_class, parse_edsm_star_class, get_body_shorthand, map_edsm_atmosphere
from pioneer.body_calc import get_body_value, get_star_value, get_starclass_k, get_planetclass_k
from pioneer.format_util import Formatter

efficiency_bonus = 1.25


class This:
    """Holds module globals."""

    def __init__(self):
        self.NAME = pioneer.const.plugin_name
        self.VERSION = semantic_version.Version(pioneer.const.plugin_version)
        self.formatter = Formatter()

        self.frame = None
        self.scroll_canvas = None
        self.scrollbar = None
        self.scrollable_frame = None
        self.label = None
        self.values_label = None
        self.total_label = None
        self.update_button: Optional[HyperlinkLabel] = None
        self.journal_label: Optional[tk.Label] = None

        # DB
        self.sql_session: Optional[Session] = None
        self.migration_failed: bool = False
        self.db_mismatch: bool = False

        # Plugin state
        self.odyssey = False
        self.game_version = semantic_version.Version('0.0.0')
        self.commander: Optional[Commander] = None
        self.system: Optional[System] = None
        self.system_status: Optional[SystemStatus] = None
        self.system_was_scanned = False
        self.system_was_mapped = False
        self.bodies: dict[str, PlanetData | StarData] = {}
        self.non_bodies: dict[str, NonBodyData] = {}
        self.body_values: dict[str, BodyValueData] = {}
        self.scans = set()
        self.main_star_value: int = 0
        self.main_star_name = ""
        self.main_star_type = "Star"
        self.map_count: int = 0
        self.planet_count: int = 0
        self.non_body_count: int = 0

        # Setting vars
        self.min_value = None
        self.shorten_values = None
        self.show_details = None
        self.show_biological = None
        self.edsm_setting = None

        # EDSM
        self.edsm_thread: Optional[threading.Thread] = None
        self.edsm_session = None
        self.edsm_bodies = None


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
            register_event_callbacks({'Scan', 'FSSDiscoveryScan', 'FSSAllBodiesFound', 'SAAScanComplete'}, process_data_event)
    return this.NAME


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
        this.frame.bind('<<PioneerEDSMData>>', edsm_data)
        if not len(sorted(plug.PLUGINS, key=lambda item: item.name == 'BioScan')):  # type: list[plug.Plugin]
            register_journal_callbacks(this.frame, 'pioneer', journal_start, journal_update, journal_end)
        this.label = tk.Label(this.frame)
        this.label.grid(row=0, column=0, columnspan=2, sticky=tk.N)
        this.scroll_canvas = tk.Canvas(this.frame, height=100, highlightthickness=0)
        this.scrollbar = ttk.Scrollbar(this.frame, orient="vertical", command=this.scroll_canvas.yview)
        this.scrollable_frame = ttk.Frame(this.scroll_canvas)
        this.scrollable_frame.bind(
            "<Configure>",
            lambda e: this.scroll_canvas.configure(
                scrollregion=this.scroll_canvas.bbox("all")
            )
        )
        this.scroll_canvas.bind("<Enter>", bind_mousewheel)
        this.scroll_canvas.bind("<Leave>", unbind_mousewheel)
        this.scroll_canvas.create_window((0, 0), window=this.scrollable_frame, anchor="nw")
        this.scroll_canvas.configure(yscrollcommand=this.scrollbar.set)
        this.values_label = ttk.Label(this.scrollable_frame)
        this.values_label.pack(fill="both", side="left")
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
        update_display()
        theme.register(this.values_label)
    return this.frame


def validate_int(val: str) -> bool:
    if val.isdigit() or val == "":
        return True
    return False


def plugin_prefs(parent: nb.Frame, cmdr: str, is_beta: bool) -> nb.Frame:
    """
    EDMC settings pane hook.
    Build settings display and hook in settings properties.

    :param parent: EDMC parent settings pane TKinter frame
    :param cmdr: Commander name (unused)
    :param is_beta: ED beta status (unused)
    :return: Plugin settings tab TKinter frame
    """

    x_padding = 10
    x_button_padding = 12
    y_padding = 2
    frame = nb.Frame(parent)
    frame.columnconfigure(2, weight=1)

    HyperlinkLabel(frame, text='Pioneer', background=nb.Label().cget('background'),
                   url='https://github.com/Silarn/EDMC-Pioneer', underline=True) \
        .grid(row=1, padx=x_padding, sticky=tk.W)
    nb.Label(frame, text = 'Version %s' % this.VERSION).grid(row=1, column=2, padx=x_padding, sticky=tk.E)

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
    ttk.Separator(frame, orient=tk.HORIZONTAL).grid(row=30, columnspan=3, pady=y_padding*2, sticky=tk.EW)
    nb.Label(frame, text='Fetch body data from EDSM:').grid(row=35, columnspan=3, padx=x_padding, sticky=tk.W)
    edsm_options = [
        "Never",
        "Always",
        "After Honk"
    ]
    nb.OptionMenu(
        frame,
        this.edsm_setting,
        this.edsm_setting.get(),
        *edsm_options
    ).grid(row=40, columnspan=3, padx=x_padding, sticky=tk.W)
    nb.Label(frame,
             text='Never: Disabled\n' +
                  'Always: Always fetch on system jump\n' +
                  'After Honk: Fetch if system is already 100% scanned',
             justify=tk.LEFT) \
        .grid(row=45, columnspan=3, padx=x_padding, sticky=tk.W)

    nb.Button(frame, text='Start / Stop Journal Parsing', command=parse_journals) \
        .grid(row=60, column=0, padx=x_padding, sticky=tk.SW)
    return frame


def prefs_changed(cmdr: str, is_beta: bool) -> None:
    config.set('pioneer_min_value', this.min_value.get())
    config.set('pioneer_shorten', this.shorten_values.get())
    this.formatter.set_shorten(this.shorten_values.get())
    config.set('pioneer_details', this.show_details.get())
    config.set('pioneer_biological', this.show_biological.get())
    config.set('pioneer_edsm', this.edsm_setting.get())
    update_display()


def parse_config() -> None:
    this.min_value = tk.IntVar(value=config.get_int(key='pioneer_min_value', default=400000))
    this.shorten_values = tk.BooleanVar(value=config.get_bool(key='pioneer_shorten', default=True))
    this.formatter.set_shorten(this.shorten_values.get())
    this.show_details = tk.BooleanVar(value=config.get_bool(key='pioneer_details', default=True))
    this.show_biological = tk.BooleanVar(value=config.get_bool(key='pioneer_biological', default=True))
    this.edsm_setting = tk.StringVar(value=config.get_str(key='pioneer_edsm', default='Never'))


def plugin_stop() -> None:
    """
    EDMC plugin stop function. Closes open threads and database sessions for clean shutdown.
    """

    if this.edsm_thread and this.edsm_thread.is_alive():
        this.edsm_thread.join()
        this.journal_stop = True


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

    progress = f'{ExploData.explo_data.journal_parse.get_progress():.1%}'
    progress = progress.rstrip('0').rstrip('.')
    this.journal_label['text'] = f'Parsing Journals: {progress}'


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
        this.values_label["text"] = "Main star not scanned.\nSystem already visited?"
        return 0, 0, 0, 0
    max_value = 0
    min_max_value = 0
    value_sum = 0
    min_value_sum = 0
    honk_sum = 0
    min_honk_sum = 0
    value_sum += this.main_star_value
    min_value_sum += this.main_star_value
    max_value += this.main_star_value
    min_max_value += this.main_star_value
    bodies_text = ""
    for body_name, body_data in sorted(this.bodies.items(), key=lambda item: item[1].get_id()):
        bodies_text += "{} - {}{}{}{}:".format(
            body_name,
            body_data.get_type() if type(body_data) is PlanetData else
            get_star_label(body_data.get_type(),
                           body_data.get_subclass(),
                           body_data.get_luminosity()),
            " <TC>" if type(body_data) is PlanetData and body_data.is_terraformable() else "",
            " -S-" if body_data.was_discovered(this.commander.id) else "",
            " -M-" if type(body_data) is PlanetData and body_data.was_mapped(this.commander.id) else "",
        ) + "\n"
        if type(body_data) is PlanetData and body_data.is_mapped(this.commander.id) is True:
            val_text = "{} - {}".format(
                this.formatter.format_credits(this.body_values[body_name].get_mapped_values()[1]),
                this.formatter.format_credits(this.body_values[body_name].get_mapped_values()[0])) \
                if this.body_values[body_name].get_mapped_values()[1] != this.body_values[body_name].get_mapped_values()[0] \
                else "{}".format(this.formatter.format_credits(this.body_values[body_name].get_mapped_values()[0]))
            bodies_text += "Current Value (Max): {}".format(val_text) + "\n"
            max_value += this.body_values[body_name].get_mapped_values()[0]
            min_max_value += this.body_values[body_name].get_mapped_values()[1]
            value_sum += this.body_values[body_name].get_mapped_values()[0]
            min_value_sum += this.body_values[body_name].get_mapped_values()[1]
        else:
            val_text = "{} - {}".format(
                this.formatter.format_credits(this.body_values[body_name].get_base_values()[1]),
                this.formatter.format_credits(this.body_values[body_name].get_base_values()[0])) \
                if this.body_values[body_name].get_base_values()[1] != this.body_values[body_name].get_base_values()[0] \
                else "{}".format(this.formatter.format_credits(this.body_values[body_name].get_base_values()[0]))
            max_val_text = "{} - {}".format(
                this.formatter.format_credits(int(this.body_values[body_name].get_mapped_values()[1] * efficiency_bonus)),
                this.formatter.format_credits(int(this.body_values[body_name].get_mapped_values()[0] * efficiency_bonus))
            ) if this.body_values[body_name].get_mapped_values()[1] != this.body_values[body_name].get_mapped_values()[0] \
                else "{}".format(
                this.formatter.format_credits(int(this.body_values[body_name].get_mapped_values()[0] * efficiency_bonus))
            )
            bodies_text += "Current Value: {}\nMax Value: {}".format(val_text, max_val_text) + "\n"
            max_value += int(this.body_values[body_name].get_mapped_values()[0] * efficiency_bonus)
            min_max_value += int(this.body_values[body_name].get_mapped_values()[1] * efficiency_bonus)
            value_sum += this.body_values[body_name].get_base_values()[0]
            min_value_sum += this.body_values[body_name].get_base_values()[1]
        if get_system_status().honked:
            if this.body_values[body_name].get_honk_values()[0] != this.body_values[body_name].get_honk_values()[1]:
                bodies_text += "Honk Value: {} - {}".format(
                    this.formatter.format_credits(this.body_values[body_name].get_honk_values()[1]),
                    this.formatter.format_credits(this.body_values[body_name].get_honk_values()[0])) + "\n"
            else:
                bodies_text += "Honk Value: {}".format(
                    this.formatter.format_credits(this.body_values[body_name].get_honk_values()[0])
                ) + "\n"
            value_sum += this.body_values[body_name].get_honk_values()[0]
            min_value_sum += this.body_values[body_name].get_honk_values()[1]
            honk_sum += this.body_values[body_name].get_honk_values()[0]
            min_honk_sum += this.body_values[body_name].get_honk_values()[1]
        max_value += this.body_values[body_name].get_honk_values()[0]
        min_max_value += this.body_values[body_name].get_honk_values()[1]
        bodies_text += "------------------" + "\n"
    this.values_label["text"] = "{}:\n   {}\n   {} + {} = {}".format(
        this.main_star_name,
        this.main_star_type,
        this.formatter.format_credits(this.main_star_value),
        this.formatter.format_credits(honk_sum) if honk_sum == min_honk_sum else "{} to {}".format(
            this.formatter.format_credits(min_honk_sum),
            this.formatter.format_credits(honk_sum)
        ),
        (this.formatter.format_credits(this.main_star_value + honk_sum)) if honk_sum == min_honk_sum else "{} to {}".format(
            this.formatter.format_credits(this.main_star_value + min_honk_sum),
            this.formatter.format_credits(this.main_star_value + honk_sum)
        )) + "\n"
    this.values_label["text"] += "------------------" + "\n"
    this.values_label["text"] += bodies_text
    status = get_system_status()
    if not this.system_was_scanned:
        total_bodies = this.non_body_count + this.system.body_count
        if status.fully_scanned:
            this.values_label["text"] += "Fully Scanned Bonus: {}".format(
                this.formatter.format_credits(total_bodies * 1000)
            ) + "\n"
            value_sum += total_bodies * 1000
            min_value_sum += total_bodies * 1000
        max_value += total_bodies * 1000
        min_max_value += total_bodies * 1000
    if not this.system_was_mapped and this.planet_count > 0:
        if status.fully_scanned and this.planet_count == this.map_count:
            this.values_label["text"] += "Fully Mapped Bonus: {}".format(
                this.formatter.format_credits(this.planet_count * 10000)) + "\n"
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


def get_body_name(fullname: str = "") -> str:
    if fullname.startswith(this.system.name + ' '):
        body_name = fullname[len(this.system.name + ' '):]
    else:
        body_name = fullname
    return body_name


def edsm_fetch() -> None:
    this.edsm_thread = threading.Thread(target=edsm_worker, name='EDSM worker', args=(this.system.name,))
    this.edsm_thread.daemon = True
    this.edsm_thread.start()


def edsm_worker(system_name: str) -> None:
    if not this.edsm_session:
        this.edsm_session = requests.Session()

    try:
        r = this.edsm_session.get('https://www.edsm.net/api-system-v1/bodies?systemName=%s' % quote(system_name),
                                  timeout=10)
        r.raise_for_status()
        this.edsm_bodies = r.json() or {}
    except requests.RequestException:
        this.edsm_bodies = None

    this.frame.event_generate('<<PioneerEDSMData>>', when='tail')


def edsm_data(event: tk.Event) -> None:
    if this.edsm_bodies is None:
        return

    for body in this.edsm_bodies.get('bodies', []):
        body_short_name = get_body_name(body['name'])
        if body_short_name not in this.bodies:
            if body['type'] == 'Star':
                try:
                    mass = body['solarMasses']
                    if body['spectralClass']:
                        star_class = body['spectralClass'][:-1]
                        subclass = body['spectralClass'][-1]
                    else:
                        star_class = parse_edsm_star_class(body['subType'])
                        subclass = 0
                    k = get_starclass_k(star_class)
                    value, honk_value = get_star_value(k, mass, False)
                    if body['isMainStar'] and this.main_star_value == 0:
                        this.main_star_value = value
                        this.main_star_type = get_star_label(star_class, subclass, body['luminosity']) + " (EDSM)"
                        this.main_star_name = "Main star" if body_short_name == this.system.name \
                            else "{} (Main star)".format(body_short_name)
                    elif not body['isMainStar']:
                        new_body = BodyValueData(body_short_name, body['bodyId'])
                        new_body.set_base_values(value, value)
                        new_body.set_mapped_values(value, value)
                        new_body.set_honk_values(honk_value, honk_value)
                        this.body_values[body_short_name] = new_body

                    star: StarData.from_journal(this.system, body_short_name, body['bodyId'], this.sql_session)
                    if body_short_name not in this.bodies:
                        star_data = StarData.from_journal(this.system, body_short_name, body['bodyId'], this.sql_session)
                    else:
                        star_data = this.bodies[body_short_name]
                    star_data.set_type(star_class).set_luminosity(body['luminosity']) \
                        .set_distance(float(body['distanceToArrival'])).set_mass(mass)
                    if subclass != 0:
                        star_data.set_subclass(subclass)
                    this.bodies[body_short_name] = star_data

                    this.system_was_scanned = True
                    this.scans.add(body_short_name)

                except Exception as e:
                    logger.error(e)

            elif body['type'] == 'Planet':
                try:
                    if body_short_name in this.bodies:
                        planet = this.bodies[body_short_name]
                    else:
                        planet = PlanetData.from_journal(this.system, body_short_name, body['bodyId'], this.sql_session)
                    odyssey_bonus = this.odyssey or this.game_version.major >= 4
                    terraformable = 'Terraformable' if body['terraformingState'] == 'Candidate for terraforming' \
                        else ''
                    distance = float(body['distanceToArrival'])
                    planet_class = map_edsm_class(body['subType'])
                    mass = float(body['earthMasses'])
                    was_discovered = planet.was_discovered(this.commander.id)
                    was_mapped = planet.was_mapped(this.commander.id)
                    this.system_was_scanned = True

                    k, kt, tm = get_planetclass_k(planet_class, terraformable == 'Terraformable')
                    value, mapped_value, honk_value, \
                        min_value, min_mapped_value, min_honk_value = \
                        get_body_value(k, kt, tm, mass, not was_discovered, not was_mapped, odyssey_bonus)

                    this.planet_count += 1
                    this.scans.add(body_short_name)
                    planet.set_type(planet_class).set_distance(distance) \
                        .set_atmosphere(map_edsm_atmosphere(body['atmosphereType'])) \
                        .set_gravity(body['gravity'] * 9.80665).set_temp(body['surfaceTemperature']) \
                        .set_mass(mass).set_terraform_state(terraformable)
                    if body['volcanismType'] == 'No volcanism':
                        volcanism = ''
                    else:
                        volcanism = body['volcanismType'].lower().capitalize() + ' volcanism'
                    planet.set_volcanism(volcanism)

                    star_search = re.search('^([A-Z]+) .+$', body_short_name)
                    if star_search:
                        for star in star_search.group(1):
                            planet.add_parent_star(star)
                    else:
                        planet.add_parent_star(this.system.name)

                    if 'materials' in body:
                        for material in body['materials']:  # type: str
                            planet.add_material(material.lower())

                    atmosphere_composition: dict[str, float] = body.get('atmosphereComposition', {})
                    if atmosphere_composition:
                        for gas, percent in atmosphere_composition.items():
                            planet.add_gas(map_edsm_atmosphere(gas), percent)

                    planet_values = BodyValueData(body_short_name, body['bodyId'])
                    planet_values.set_base_values(value, min_value)
                    planet_values.set_honk_values(honk_value, min_honk_value)
                    if planet_values.get_mapped_values()[1] == 0:
                        planet_values.set_mapped_values(int(mapped_value), int(min_mapped_value))
                    else:
                        planet_values.set_mapped_values(int(mapped_value * efficiency_bonus),
                                                        int(min_mapped_value * efficiency_bonus))

                    this.bodies[body_short_name] = planet
                    this.body_values[body_short_name] = planet_values

                except Exception as e:
                    logger.error(e)

    calc_counts()
    update_display()


def reset() -> None:
    """
    Reset system data, typically when the location changes
    """

    this.main_star_value = 0
    this.main_star_type = "Star"
    this.main_star_name = ""
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

    if this.migration_failed:
        return ''

    system_changed = False
    # this.game_version = semantic_version.Version.coerce(state.get('GameVersion', '0.0.0'))
    # this.odyssey = state.get('Odyssey', False)
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
            this.main_star_name = "Main star" if this.system == main_star.name \
                else "{} (Main star)".format(main_star.name)
            this.main_star_type = get_star_label(main_star.type, main_star.subclass, main_star.luminosity)
            this.bodies.pop(main_star.name, None)

    this.game_version = semantic_version.Version.coerce(state.get('GameVersion', '0.0.0'))
    this.odyssey = state.get('Odyssey', False)

    if system_changed:
        this.scroll_canvas.yview_moveto(0.0)
        if this.edsm_setting.get() == "Always":
            edsm_fetch()

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
            elif 'PlanetClass' in entry and entry['PlanetClass']:
                body = PlanetData.from_journal(this.system, body_short_name, entry['BodyID'], this.sql_session)
            else:
                non_body = NonBodyData.from_journal(this.system, body_short_name, entry['BodyID'], this.sql_session)
                this.non_bodies[body_short_name] = non_body
            process_body_values(body)
            update_display()
        case 'FSSDiscoveryScan':
            if entry['Progress'] == 1.0 and not get_system_status().fully_scanned:
                get_system_status().fully_scanned = True
                this.sql_session.commit()
                if this.edsm_setting.get() == "After Honk":
                    edsm_fetch()
            update_display()
        case 'FSSAllBodiesFound':
            update_display()
        case 'SAAScanComplete':
            body_short_name = get_body_name(entry['BodyName'])
            if body_short_name.endswith('Ring') or body_short_name.find('Belt Cluster') != -1:
                return
            if body_short_name in this.bodies:
                planet = this.bodies[body_short_name]
            else:
                planet = PlanetData.from_journal(this.system, body_short_name, entry['BodyID'], this.sql_session)
            if body_short_name in this.body_values:
                body_value = this.body_values[body_short_name]
                map_val, map_val_max = body_value.get_mapped_values()
                final_val = (
                    int(map_val * efficiency_bonus) if planet.was_efficient(this.commander.id) else map_val,
                    int(map_val_max * efficiency_bonus) if planet.was_efficient(this.commander.id) else map_val_max
                )
                body_value.set_mapped_values(final_val[0], final_val[1])
            else:
                body_value = BodyValueData(body_short_name, entry['BodyID'])
            this.bodies[body_short_name] = planet
            this.body_values[body_short_name] = body_value
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
            this.main_star_name = "Main star" if this.system.name == body.get_name() \
                else "{} (Main star)".format(body.get_name())
            this.main_star_type = get_star_label(body.get_type(), body.get_subclass(), body.get_luminosity())
        else:
            body_value = BodyValueData(body.get_name(), body.get_id())
            body_value.set_base_values(value, value).set_mapped_values(value, value).set_honk_values(honk_value, honk_value)
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
            if body_value.get_mapped_values()[1] == 0:
                body_value.set_mapped_values(int(mapped_value), int(min_mapped_value))
            else:
                body_value.set_mapped_values(int(mapped_value * efficiency_bonus),
                                             int(min_mapped_value * efficiency_bonus))
            this.body_values[body.get_name()] = body_value

    if body.get_distance() > 0.0:
        this.bodies[body.get_name()] = body


def get_system_status() -> Optional[SystemStatus]:
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
    return this.system_status


def update_display() -> None:
    system_status = get_system_status()
    if not system_status:
        this.label['text'] = 'Pioneer: Waiting for Data'
        return

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
                   (body_name.upper(),
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
            text += "\n"

        text += 'B#: {} NB#: {}'.format(this.system.body_count, this.system.non_body_count)
        this.label['text'] = text
    else:
        this.label['text'] = 'Pioneer: Nothing Scanned'

    total_value, min_total_value, max_value, min_max_value = calc_system_value()
    if total_value != min_total_value:
        this.total_label['text'] = 'Estimated System Value: {} to {}'.format(
            this.formatter.format_credits(min_total_value), this.formatter.format_credits(total_value))
        this.total_label['text'] += '\nMaximum System Value: {} to {}'.format(
            this.formatter.format_credits(min_max_value), this.formatter.format_credits(max_value))
    else:
        this.total_label['text'] = 'Estimated System Value: {}'.format(
            this.formatter.format_credits(total_value) if total_value > 0 else "N/A")
        this.total_label['text'] += '\nMaximum System Value: {}'.format(
            this.formatter.format_credits(max_value) if total_value > 0 else "N/A")

    if this.show_details.get():
        this.scroll_canvas.grid()
        this.scrollbar.grid()
    else:
        this.scroll_canvas.grid_remove()
        this.scrollbar.grid_remove()


def bind_mousewheel(event: tk.Event) -> None:
    if sys.platform in ("linux", "cygwin", "msys"):
        this.scroll_canvas.bind_all('<Button-4>', on_mousewheel)
        this.scroll_canvas.bind_all('<Button-5>', on_mousewheel)
    else:
        this.scroll_canvas.bind_all('<MouseWheel>', on_mousewheel)


def unbind_mousewheel(event: tk.Event) -> None:
    if sys.platform in ("linux", "cygwin", "msys"):
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
        this.scroll_canvas.xview_scroll(scroll, "units")
    else:
        this.scroll_canvas.yview_scroll(scroll, "units")
