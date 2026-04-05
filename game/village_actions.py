import json
import logging
import time
from codecs import decode
from core.extractors import Extractor
from core.templates import TemplateManager
from game.attack import AttackManager
from game.buildingmanager import BuildingManager
from game.map import Map
from game.reports import ReportManager
from game.snobber import SnobManager
from game.troopmanager import TroopManager

class VillageActionsMixin:
    def run_quest_actions(self, config):
        if self.get_config(section="world", parameter="quests_enabled", default=False):
            if self.get_quests():
                return self.run(config=config)
            self.get_quest_rewards()

    def run_builder(self):
        if not self.builder:
            self.builder = BuildingManager(wrapper=self.wrapper, village_id=self.village_id)
            self.builder.resman = self.resman
        self.build_config = self.get_village_config(self.village_id, parameter="building", default="purple_predator")
        if self.build_config is False: return
        new_queue = TemplateManager.get_template(category="builder", template=self.build_config)
        if self.builder.raw_template != new_queue:
            self.builder.queue = new_queue; self.builder.raw_template = new_queue
        self.builder.max_lookahead = self.get_config(section="building", parameter="max_lookahead", default=2)
        self.builder.max_queue_len = self.get_config(section="building", parameter="max_queued_items", default=2)
        self.builder.start_update(overview_game_data=self.game_data, overview_html=self.overview_html, build=self.get_config(section="building", parameter="manage_buildings", default=True))

    def run_unit_upgrades(self):
        if self.get_config(section="units", parameter="upgrade", default=False):
            self.units.attempt_upgrade()

    def run_snob_recruit(self):
        if self.get_village_config(self.village_id, parameter="snobs", default=None) and self.builder.levels.get("snob", 0) > 0:
            if not self.snobman:
                self.snobman = SnobManager(wrapper=self.wrapper, village_id=self.village_id)
                self.snobman.troop_manager = self.units; self.snobman.resman = self.resman
            self.snobman.wanted = self.get_village_config(self.village_id, parameter="snobs", default=0)
            self.snobman.building_level = self.builder.get_level("snob"); self.snobman.run()

    def do_recruit(self):
        if self.get_config(section="units", parameter="recruit", default=False):
            self.units.can_fix_queue = self.get_config(section="units", parameter="remove_manual_queued", default=False)
            if self.get_village_config(self.village_id, parameter="prioritize_building", default=False) and not self.resman.can_recruit():
                for x in list(self.resman.requested.keys()):
                    if "recruitment_" in x: self.resman.requested.pop(f"{x}", None)
            else:
                for building in self.units.wanted:
                    if self.builder.get_level(building): self.units.start_update(building, self.disabled_units)

    def run_farming(self):
        if not self.forced_peace and self.units.can_attack:
            if not self.area: self.area = Map(wrapper=self.wrapper, village_id=self.village_id)
            rad = self.get_config(section="farms", parameter="map_scan_radius", default=0)
            s_rad = self.get_config(section="farms", parameter="search_radius", default=50)
            self.area.get_map(radius=rad, fetch_delay=self.get_config(section="farms", parameter="map_scan_delay", default=8), search_radius=s_rad)
            if self.area.villages:
                if not self.attack:
                    self.attack = AttackManager(wrapper=self.wrapper, village_id=self.village_id, troopmanager=self.units, map=self.area)
                    self.attack.repman = self.rep_man
                self.set_farm_options(); self.attack.run()

    def do_gather(self):
        if not self.scavenging:
            return
        
        # Don't scavenge if we are under attack to keep troops at home for defense
        if self.def_man and self.def_man.under_attack:
            return

        self.scavenging.run()

    def go_manage_market(self):
        if self.get_config(section="market", parameter="auto_trade", default=False) and self.builder.get_level("market"):
            self.resman.manage_market(drop_existing=self.get_config(section="market", parameter="auto_remove", default=True))
        if self.get_config(section="world", parameter="trade_for_premium", default=False):
            self.resman.do_premium_trade = True; self.resman.do_premium_stuff()

    def get_quests(self):
        result = Extractor.get_quests(self.wrapper.last_response)
        if result:
            return bool(self.wrapper.get_api_action(action="quest_complete", village_id=self.village_id, params={"quest": result, "skip": "false"}))
        return False

    def get_quest_rewards(self):
        result = self.wrapper.get_api_data(
            action="quest_popup",
            village_id=self.village_id,
            params={"screen": 'new_quests', "tab": "main-tab", "quest": 0},
        )
        if result is None:
            self.logger.warning("Failed to fetch quest reward data from API")
            return False
            
        # The data is escaped for JS, so unescape it before sending it to the extractor.
        rewards = Extractor.get_quest_rewards(decode(result["response"]["dialog"], 'unicode-escape'))
        for reward in rewards:
            # First check if there is enough room for storing the reward
            for t_resource in reward["reward"]:
                if self.resman.storage - self.resman.actual[t_resource] < reward["reward"][t_resource]:
                    self.logger.info(f"Not enough room to store the {t_resource} part of the reward")
                    return False

            qres = self.wrapper.post_api_data(
                action="claim_reward",
                village_id=self.village_id,
                params={"screen": "new_quests"},
                data={"reward_id": reward["id"]}
            )
            if qres:
                if qres['response'] == False:
                    self.logger.debug(f"Error getting reward! {qres}")
                    return False
                else:
                    self.logger.info("Got quest reward: %s" % str(reward))
                    for t_resource in reward["reward"]:
                        self.resman.actual[t_resource] += reward["reward"][t_resource]

        self.logger.debug("There where no (more) quest rewards")
        return len(rewards) > 0
