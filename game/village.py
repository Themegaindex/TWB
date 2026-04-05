import json
import logging
import time
from datetime import datetime
from core.extractors import Extractor
from core.twstats import TwStats
from core.templates import TemplateManager
from game.attack import AttackManager
from game.buildingmanager import BuildingManager
from game.defence_manager import DefenceManager
from game.map import Map
from game.reports import ReportManager
from game.resources import ResourceManager
from game.snobber import SnobManager
from game.troopmanager import TroopManager
from core.database import DatabaseManager, DBVillage, DBVillageSettings
from game.village_config import VillageConfigMixin
from game.village_actions import VillageActionsMixin


from game.scavenging import ScavengingManager


class Village(VillageConfigMixin, VillageActionsMixin):
    village_id = None
    builder = None
    units = None
    wrapper = None
    game_data = {}
    logger = None
    area = None
    snobman = None
    attack = None
    resman = None
    def_man = None
    rep_man = None
    scavenging = None
    config = None
    disabled_units = []
    overview_html = None
    twp = TwStats()
    forced_peace = False
    forced_peace_today = False
    forced_peace_today_start = None
    last_attack = None
    current_unit_entry = None

    def __init__(self, village_id=None, wrapper=None):
        self.village_id = village_id
        self.wrapper = wrapper

    def update_pre_run(self):
        if not self.resman: self.resman = ResourceManager(wrapper=self.wrapper, village_id=self.village_id)
        self.resman.update(self.game_data)
        if not self.rep_man: self.rep_man = ReportManager(wrapper=self.wrapper, village_id=self.village_id)
        self.rep_man.read(full_run=False, overview_html=self.overview_html)
        if not self.def_man: self.def_man = DefenceManager(wrapper=self.wrapper, village_id=self.village_id); self.def_man.map = self.area
        if not self.def_man.units and self.units: self.def_man.units = self.units
        
        if self.get_village_config(self.village_id, parameter="gather_enabled", default=False):
            if not self.scavenging:
                # We pass the full village config or just the template? 
                # ScavengingManager expects the village_template dict structure.
                # Let's provide a merged config for the village.
                v_config = self.config.get("village_template", {}).copy()
                if self.village_id in self.config.get("villages", {}):
                    v_config.update(self.config["villages"][self.village_id])
                
                self.scavenging = ScavengingManager(
                    village_id=self.village_id,
                    config=v_config,
                    wrapper=self.wrapper
                )

    def run(self, config=None):
        self.config = config; data = self.village_init()
        if not self.game_data: return False
        self.set_world_config()
        if not self.get_village_config(self.village_id, parameter="managed", default=False): return False
        self.update_pre_run(); self.setup_defence_manager(data)
        self.run_quest_actions(config); self.check_forced_peace(); self.run_builder()
        self.units_get_template(); self.set_unit_wanted_levels()
        self.units.update_totals(self.game_data, self.overview_html)
        self.run_unit_upgrades(); self.run_snob_recruit(); self.do_recruit()
        self.run_farming(); self.do_gather(); self.go_manage_market()
        self.set_cache_vars()

    def check_forced_peace(self):
        forced_peace_times = self.get_config(section="farms", parameter="forced_peace_times", default=[])
        self.forced_peace = False; self.forced_peace_today = False; self.forced_peace_today_start = None
        for time_pair in forced_peace_times:
            start_dt = datetime.strptime(time_pair["start"], "%d.%m.%y %H:%M:%S")
            end_dt = datetime.strptime(time_pair["end"], "%d.%m.%y %H:%M:%S")
            now = datetime.now()
            if start_dt.date() == now.date():
                self.forced_peace_today = True; self.forced_peace_today_start = start_dt
            if start_dt < now < end_dt:
                self.logger.debug("Forced peace time detected!"); self.forced_peace = True; break

    def setup_defence_manager(self, data):
        self.def_man.support_factor = self.get_village_config(self.village_id, parameter="support_others_factor", default=0.25)
        self.def_man.support_max_villages = self.get_village_config(self.village_id, parameter="support_others_max_villages", default=2)
        self.def_man.allow_support_send = self.get_village_config(self.village_id, parameter="support_others", default=False)
        self.def_man.allow_support_recv = self.get_village_config(self.village_id, parameter="request_support_on_attack", default=False)
        self.def_man.auto_evacuate = self.get_village_config(self.village_id, parameter="evacuate_fragile_units_on_attack", default=False)

        self.def_man.update(self.overview_html, with_defence=self.get_config(section="units", parameter="manage_defence", default=False))

    def units_get_template(self):
        if not self.units: self.units = TroopManager(wrapper=self.wrapper, village_id=self.village_id); self.units.resman = self.resman
        unit_config = self.get_village_config(self.village_id, parameter="units", default="basic")
        self.units.template = TemplateManager.get_template(category="troops", template=unit_config, output_json=True)

    def set_unit_wanted_levels(self):
        self.current_unit_entry = self.units.get_template_action(self.builder.levels)
        if self.current_unit_entry: self.units.wanted = self.current_unit_entry["build"]

    def set_farm_options(self):
        self.attack.farm_radius = self.get_config(section="farms", parameter="search_radius", default=50)
        self.attack.smart_farming = self.get_config(section="farms", parameter="smart_farming", default=False)
        self.attack.smart_farming_priority = self.get_config(section="farms", parameter="smart_farming_priority", default=[])
        self.attack.min_farm_capacity = self.get_config(section="farms", parameter="min_farm_capacity", default=0)
        self.attack.min_farm_units = self.get_config(section="farms", parameter="min_farm_units", default=0)
        if self.current_unit_entry: self.attack.template = self.current_unit_entry["farm"]

    def set_cache_vars(self):
        village_entry = {
            "name": self.game_data["village"]["name"],
            "resources": self.resman.actual,
            "building_levels": self.builder.levels,
            "available_troops": self.units.troops,
            "troops": self.units.total_troops,
            "last_run": int(time.time()),
        }
        DatabaseManager.upsert_village(self.village_id, name=self.game_data["village"]["name"])
        # Report data for dashboard
        for dt, val in [("village.resources", self.resman.actual), ("village.buildings", self.builder.levels), ("village.troops", self.units.total_troops)]:
            self.wrapper.reporter.add_data(self.village_id, data_type=dt, data=json.dumps(val))
