"""
Anything that has to do with the recruiting of troops
"""
import logging
import time
from core.extractors import Extractor
from game.resources import ResourceManager
from game.gather_manager import GatherMixin
from game.recruit_manager import RecruitMixin


class TroopManager(GatherMixin, RecruitMixin):
    """
    Troopmanager class
    """
    can_recruit = True
    can_attack = True
    can_dodge = False
    can_scout = True
    can_farm = True
    can_gather = True
    can_fix_queue = True
    randomize_unit_queue = True

    queue = {}
    troops = {}
    total_troops = {}
    _research_wait = 0

    wrapper = None
    village_id = None
    recruit_data = {}
    game_data = {}
    logger = None
    max_batch_size = 50

    _waits = {}
    wanted = {"barracks": {}}
    wanted_levels = {}
    last_gather = 0
    resman = None
    template = None

    carry_capacity = {
        "spear": 25, "sword": 15, "axe": 10, "archer": 10, "spy": 0, "light": 80,
        "marcher": 50, "heavy": 50, "ram": 0, "catapult": 0, "knight": 100, "snob": 0,
    }

    def __init__(self, wrapper=None, village_id=None):
        self.wrapper = wrapper
        self.village_id = village_id
        self.wait_for = {village_id: {"barracks": 0, "stable": 0, "garage": 0}}
        self.queue = {}
        if not self.resman:
            self.resman = ResourceManager(wrapper=self.wrapper, village_id=self.village_id)

    def update_totals(self, overview_game_data, overview_html):
        self.game_data = overview_game_data
        if self.resman:
            self.resman.requested["research"] = {}
        if not self.logger:
            self.logger = logging.getLogger(f"Recruitment: {self.game_data['village']['name']}")
        
        extracted_units = Extractor.units_in_village(overview_html)
        if not extracted_units:
            place_url = f"game.php?village={self.village_id}&screen=place&mode=units"
            place_data = self.wrapper.get_url(url=place_url)
            if place_data:
                extracted_units = Extractor.units_in_village(place_data.text)
        
        self.troops = {k: v for k, v in extracted_units}
        self.total_troops = {}
        for k, v in Extractor.units_in_total(overview_html):
            self.total_troops[k] = self.total_troops.get(k, 0) + int(v)

        # Update recruitment queue data to avoid over-recruiting
        self.queue = {}
        for building in ["barracks", "stable", "garage"]:
            # We need to visit each building to get the accurate queue
            # (Overview only shows active building, not all queues)
            url = f"game.php?village={self.village_id}&screen={building}"
            res = self.wrapper.get_url(url=url)
            if res:
                q_detailed = Extractor.active_recruit_queue_detailed(res.text)
                for item in q_detailed:
                    u = item["unit"]
                    self.queue[u] = self.queue.get(u, 0) + item["amount"]
                    # Add queue to total_troops so the bot knows they are 'coming'
                    self.total_troops[u] = self.total_troops.get(u, 0) + item["amount"]
        
        if not self.total_troops:
            train_url = f"game.php?village={self.village_id}&screen=train"
            train_data = self.wrapper.get_url(url=train_url)
            if train_data:
                r_data = Extractor.recruit_data(train_data.text)
                if r_data:
                    for un, un_data in r_data.items():
                        if int(un_data.get("in_total", 0)) > 0:
                            self.total_troops[un] = self.total_troops.get(un, 0) + int(un_data["in_total"])
                        if int(un_data.get("in_village", 0)) > 0:
                            self.troops[un] = str(un_data["in_village"])

    def readable_ts(self, seconds):
        seconds = (seconds - int(time.time())) % (24 * 3600)
        return "%d:%02d:%02d" % (seconds // 3600, (seconds % 3600) // 60, seconds % 60)
