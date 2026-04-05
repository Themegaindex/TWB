import logging
import math
import random
import time
from core.extractors import Extractor

class RecruitMixin:
    def start_update(self, building="barracks", disabled_units=None):
        if disabled_units is None: disabled_units = []
        if self.wait_for[self.village_id][building] > time.time():
            return False
        run_selection = list(self.wanted[building].keys())
        if self.randomize_unit_queue: random.shuffle(run_selection)
        resource_failed = False
        for wanted in run_selection:
            if wanted in disabled_units or resource_failed: continue
            current = self.total_troops.get(wanted, 0)
            target = self.wanted[building][wanted]
            if target > current:
                if self.recruit(wanted, target - current, building=building): return True
                if self.recruit_data and wanted in self.recruit_data:
                    if self.get_min_possible(self.recruit_data[wanted]) == 0: resource_failed = True
        return False

    def get_min_possible(self, entry):
        return min([
            math.floor(self.game_data["village"]["wood"] / entry["wood"]),
            math.floor(self.game_data["village"]["stone"] / entry["stone"]),
            math.floor(self.game_data["village"]["iron"] / entry["iron"]),
            math.floor((self.game_data["village"]["pop_max"] - self.game_data["village"]["pop"]) / entry["pop"]),
        ])

    def get_template_action(self, levels):
        last = None
        for x in self.template:
            if x["building"] not in levels or x["level"] > levels[x["building"]]: return last
            last = x
            if "upgrades" in x:
                for unit, level in x["upgrades"].items():
                    if unit not in self.wanted_levels or level > self.wanted_levels[unit]:
                        self.wanted_levels[unit] = level
        return last

    def research_time(self, time_str):
        parts = [int(x) for x in time_str.split(":")]
        return parts[2] + (parts[1] * 60) + (parts[0] * 3600)

    def attempt_upgrade(self):
        if self._research_wait > time.time() or not self.wanted_levels: return False
        result = self.wrapper.get_action(village_id=self.village_id, action="smith")
        smith_data = Extractor.smith_data(result)
        if not smith_data: return False
        for unit_type, wanted_level in self.wanted_levels.items():
            if unit_type not in smith_data["available"]: continue
            data = smith_data["available"][unit_type]
            if int(data["level"]) < wanted_level and data.get("can_research"):
                if data.get("research_error") or data.get("error_buildings"): continue
                if self.attempt_research(unit_type, smith_data=smith_data):
                    self.logger.info(f"Started smith upgrade of {unit_type} {int(data['level'])} -> {int(data['level']) + 1}")
                    return True
        return False

    def attempt_research(self, unit_type, smith_data=None):
        if not smith_data:
            result = self.wrapper.get_action(village_id=self.village_id, action="smith")
            smith_data = Extractor.smith_data(result)
        if not smith_data or unit_type not in smith_data["available"]: return False
        data = smith_data["available"][unit_type]
        if not data.get("can_research") or data.get("research_error") or data.get("error_buildings"):
            if data.get("research_error"):
                for r in ["wood", "stone", "iron"]:
                    if data[r] > self.game_data["village"][r]:
                        self.resman.request(source="research", resource=r, amount=data[r] - self.game_data["village"][r])
            return False
        if data.get("level_highest") != 0 and data.get("level") == data.get("level_highest"): return False
        res = self.wrapper.get_api_action(village_id=self.village_id, action="research", params={"screen": "smith"}, data={"tech_id": unit_type, "source": self.village_id, "h": self.wrapper.last_h})
        if res and "research_time" in data:
            self._research_wait = time.time() + self.research_time(data["research_time"])
        return bool(res)

    def recruit(self, unit_type, amount=10, wait_for=False, building="barracks"):
        data = self.wrapper.get_action(action=building, village_id=self.village_id)
        
        # Check if the specific unit type is already in queue
        detailed_queue = Extractor.active_recruit_queue_detailed(data)
        unit_in_queue = any(q["unit"] == unit_type for q in detailed_queue)
        
        if detailed_queue:
            if not self.can_fix_queue: 
                # If we don't want to fix queue, but the specific unit is already training, stop here
                if unit_in_queue:
                    return True
                # If building has a queue but not for our unit, we might still want to add to it 
                # (but Tribal Wars usually allows only 1 batch per unit type in queue or similar)
            else:
                # If we can fix queue, remove entries for THIS unit type or all if needed
                for entry in detailed_queue:
                    if entry["unit"] == unit_type or self.can_fix_queue == "all":
                        self.wrapper.get_api_action(action="cancel", params={"screen": building}, data={"id": entry["order_id"]}, village_id=self.village_id)
                return self.recruit(unit_type, amount, wait_for, building)

        self.recruit_data = Extractor.recruit_data(data)
        self.game_data = Extractor.game_state(data)
        amount = min(amount, self.max_batch_size)
        if unit_type not in self.recruit_data or not self.recruit_data[unit_type].get("requirements_met"):
            self.attempt_research(unit_type)
            return False
        res = self.recruit_data[unit_type]
        get_min = self.get_min_possible(res)
        if get_min == 0 or (wait_for and get_min < amount):
            self.reserve_resources(res, amount, get_min, unit_type)
            return False
        amount = min(amount, get_min)
        if f"recruitment_{unit_type}" in self.resman.requested: self.resman.requested.pop(f"recruitment_{unit_type}", None)
        return self.wrapper.get_api_action(village_id=self.village_id, action="train", params={"screen": building, "mode": "train"}, data={"units[%s]" % unit_type: str(amount)})

    def reserve_resources(self, resources, wanted_times, has_times, unit_type):
        for r in ["wood", "stone", "iron"]:
            needed = (wanted_times - has_times) * resources[r]
            self.resman.request(source="recruitment_%s" % unit_type, resource=r, amount=needed)
