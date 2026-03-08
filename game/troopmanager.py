"""
Anything that has to do with the recruiting of troops
"""
import logging
import math
import random
import time

from core.extractors import Extractor
from game.resources import ResourceManager


class TroopManager:
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

    queue = []
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

    # Maps troops to the building they are created from
    unit_building = {
        "spear": "barracks",
        "sword": "barracks",
        "axe": "barracks",
        "archer": "barracks",
        "spy": "stable",
        "light": "stable",
        "marcher": "stable",
        "heavy": "stable",
        "ram": "garage",
        "catapult": "garage",
    }

    wanted_levels = {}

    last_gather = 0

    resman = None
    template = None

    carry_capacity = {
        "spear": 25,
        "sword": 15,
        "axe": 10,
        "archer": 10,
        "spy": 0,
        "light": 80,
        "marcher": 50,
        "heavy": 50,
        "ram": 0,
        "catapult": 0,
        "knight": 100,
        "snob": 0,
    }

    def __init__(self, wrapper=None, village_id=None):
        """
        Create the troop manager
        """
        self.wrapper = wrapper
        self.village_id = village_id
        self.wait_for = {}
        self.wait_for[village_id] = {"barracks": 0, "stable": 0, "garage": 0}
        if not self.resman:
            self.resman = ResourceManager(
                wrapper=self.wrapper, village_id=self.village_id
            )

    # --- PERFORMANCE (POINT 2) ---
    def update_totals(self, overview_game_data, overview_html):
        """
        Updates the total amount of recruited units
        Uses cached game_data and overview_html from Village.run
        """
        # Use cached game_data
        self.game_data = overview_game_data
        # --- END PERFORMANCE ---

        if self.resman:
            if "research" in self.resman.requested:
                # new run, remove request
                self.resman.requested["research"] = {}

        if not self.logger:
            village_name = self.game_data["village"]["name"]
            self.logger = logging.getLogger(f"Recruitment: {village_name}")
        self.troops = {}

        # --- PERFORMANCE (POINT 2) ---
        # Try to extract units from cached overview_html first
        extracted_units = Extractor.units_in_village(overview_html)
        self.logger.debug(f"Extractor.units_in_village from overview_html returned: {extracted_units}")
        
        # If overview_html doesn't contain units (units_home table), fetch from place screen
        if not extracted_units:
            self.logger.debug("No units found in overview_html, fetching from place screen")
            place_url = f"game.php?village={self.village_id}&screen=place&mode=units"
            place_data = self.wrapper.get_url(url=place_url)
            if place_data:
                extracted_units = Extractor.units_in_village(place_data.text)
                self.logger.debug(f"Extractor.units_in_village from place screen returned: {extracted_units}")
        
        for u in extracted_units:
            k, v = u
            self.troops[k] = v
        # --- END PERFORMANCE ---

        self.logger.debug("Units in village: %s", str(self.troops))

        if not self.can_recruit:
            return

        self.total_troops = {}
        # --- PERFORMANCE (POINT 2) ---
        # Use cached overview_html to extract total units
        for u in Extractor.units_in_total(overview_html):
            k, v = u
            if k in self.total_troops:
                self.total_troops[k] = self.total_troops[k] + int(v)
            else:
                self.total_troops[k] = int(v)
        
        # --- BUGFIX: Fallback if all troops are missing from overview (e.g., they are outside the village)
        if not self.total_troops:
            self.logger.debug("No total troops found in overview. Falling back to train screen unit manager values.")
            train_url = f"game.php?village={self.village_id}&screen=train"
            train_data = self.wrapper.get_url(url=train_url)
            if train_data:
                r_data = Extractor.recruit_data(train_data.text)
                if r_data:
                    for un, un_data in r_data.items():
                        if "in_total" in un_data and int(un_data["in_total"]) > 0:
                            self.total_troops[un] = int(un_data["in_total"])
                        # Optional: also update troops in home if needed
                        if "in_village" in un_data and int(un_data["in_village"]) > 0:
                            self.troops[un] = str(un_data["in_village"])
        # --- END BUGFIX ---
        # --- END PERFORMANCE ---
        self.logger.debug("Village units total: %s", str(self.total_troops))


    def start_update(self, building="barracks", disabled_units=None):
        """
        Starts the unit update for a building
        """
        if disabled_units is None:
            disabled_units = []
        if self.wait_for[self.village_id][building] > time.time():
            human_ts = self.readable_ts(self.wait_for[self.village_id][building])
            self.logger.info(
                "%s still busy for %s",
                building, human_ts
            )
            return False

        run_selection = list(self.wanted[building].keys())
        if self.randomize_unit_queue:
            random.shuffle(run_selection)

        # Track if we've already failed due to insufficient resources
        resource_check_failed = False

        for wanted in run_selection:
            # Ignore disabled units
            if wanted in disabled_units:
                continue

            # Skip if we already know resources are insufficient
            if resource_check_failed:
                self.logger.debug(
                    "Skipping %s recruitment attempt - insufficient resources detected earlier",
                    wanted
                )
                continue

            if wanted not in self.total_troops:
                result = self.recruit(
                    wanted, self.wanted[building][wanted], building=building
                )
                if result:
                    return True
                # Check if failure was due to resources by looking at recruit_data
                if self.recruit_data and wanted in self.recruit_data:
                    get_min = self.get_min_possible(self.recruit_data[wanted])
                    if get_min == 0:
                        resource_check_failed = True
                continue

            if self.wanted[building][wanted] > self.total_troops[wanted]:
                result = self.recruit(
                    wanted,
                    self.wanted[building][wanted] - self.total_troops[wanted],
                    building=building,
                    )
                if result:
                    return True
                # Check if failure was due to resources by looking at recruit_data
                if self.recruit_data and wanted in self.recruit_data:
                    get_min = self.get_min_possible(self.recruit_data[wanted])
                    if get_min == 0:
                        resource_check_failed = True

        self.logger.info("Recruitment:%s up-to-date", building)
        return False

    def get_min_possible(self, entry):
        """
        Calculates which units are needed the most
        To get some balance of the total amount
        """
        return min(
            [
                math.floor(self.game_data["village"]["wood"] / entry["wood"]),
                math.floor(self.game_data["village"]["stone"] / entry["stone"]),
                math.floor(self.game_data["village"]["iron"] / entry["iron"]),
                math.floor(
                    (
                            self.game_data["village"]["pop_max"]
                            - self.game_data["village"]["pop"]
                    )
                    / entry["pop"]
                ),
            ]
        )

    def get_template_action(self, levels):
        """
        Read data from templates and determine the troops based op building progression
        """
        last = None
        wanted_upgrades = {}
        for x in self.template:
            if x["building"] not in levels:
                return last

            if x["level"] > levels[x["building"]]:
                return last

            last = x
            if "upgrades" in x:
                for unit in x["upgrades"]:
                    if (
                            unit not in wanted_upgrades
                            or x["upgrades"][unit] > wanted_upgrades[unit]
                    ):
                        wanted_upgrades[unit] = x["upgrades"][unit]

            self.wanted_levels = wanted_upgrades
        return last

    def research_time(self, time_str):
        """
        Calculates unit research time
        """
        parts = [int(x) for x in time_str.split(":")]
        return parts[2] + (parts[1] * 60) + (parts[0] * 60 * 60)

    def attempt_upgrade(self):
        """
        Attempts to upgrade or research a (new) unit type
        """
        self.logger.debug("Managing Upgrades")
        if self._research_wait > time.time():
            self.logger.debug(
                "Smith still busy for %d seconds", int(self._research_wait - time.time())
            )
            return
        unit_levels = self.wanted_levels
        if not unit_levels:
            self.logger.debug("Not upgrading because nothing is requested")
            return
        result = self.wrapper.get_action(village_id=self.village_id, action="smith")
        smith_data = Extractor.smith_data(result)
        if not smith_data:
            self.logger.debug("Error reading smith data")
            return False
        for unit_type in unit_levels:
            if not smith_data or unit_type not in smith_data["available"]:
                self.logger.warning(
                    "Unit %s does not appear to be available or smith not built yet", unit_type
                )
                continue
            wanted_level = unit_levels[unit_type]
            current_level = int(smith_data["available"][unit_type]["level"])
            data = smith_data["available"][unit_type]

            if (
                    current_level < wanted_level
                    and "can_research" in data
                    and data["can_research"]
            ):
                if "research_error" in data and data["research_error"]:
                    # Add needed resources to res manager?
                    r = True
                    if data["wood"] > self.game_data["village"]["wood"]:
                        req = data["wood"] - self.game_data["village"]["wood"]
                        self.resman.request(source="research", resource="wood", amount=req)
                        r = False
                    if data["stone"] > self.game_data["village"]["stone"]:
                        req = data["stone"] - self.game_data["village"]["stone"]
                        self.resman.request(source="research", resource="stone", amount=req)
                        r = False
                    if data["iron"] > self.game_data["village"]["iron"]:
                        req = data["iron"] - self.game_data["village"]["iron"]
                        self.resman.request(source="research", resource="iron", amount=req)
                        r = False
                    if not r:
                        self.logger.debug("Skipping research of %s because of research error (not enough resources)", unit_type)
                        self.logger.debug("Research needs resources")
                    else:
                        self.logger.debug(
                            "Skipping research of %s because of research error", unit_type
                        )
                    continue
                if "error_buildings" in data and data["error_buildings"]:
                    self.logger.debug(
                        "Skipping research of %s because of building error", unit_type
                    )
                    continue

                attempt = self.attempt_research(unit_type, smith_data=smith_data)
                if attempt:
                    self.logger.info(
                        "Started smith upgrade of %s %d -> %d",
                        unit_type, current_level, current_level + 1
                    )
                    self.wrapper.reporter.report(
                        self.village_id,
                        "TWB_UPGRADE",
                        "Started smith upgrade of %s %d -> %d"
                        % (unit_type, current_level, current_level + 1),
                        )
                    return True
        return False

    def attempt_research(self, unit_type, smith_data=None):
        if not smith_data:
            result = self.wrapper.get_action(village_id=self.village_id, action="smith")
            smith_data = Extractor.smith_data(result)
        if not smith_data or unit_type not in smith_data["available"]:
            self.logger.warning(
                "Unit %s does not appear to be available or smith not built yet", unit_type
            )
            return
        data = smith_data["available"][unit_type]
        if "can_research" in data and data["can_research"]:
            if "research_error" in data and data["research_error"]:
                # Add needed resources to res manager?
                r = True
                if data["wood"] > self.game_data["village"]["wood"]:
                    req = data["wood"] - self.game_data["village"]["wood"]
                    self.resman.request(source="research", resource="wood", amount=req)
                    r = False
                if data["stone"] > self.game_data["village"]["stone"]:
                    req = data["stone"] - self.game_data["village"]["stone"]
                    self.resman.request(source="research", resource="stone", amount=req)
                    r = False
                if data["iron"] > self.game_data["village"]["iron"]:
                    req = data["iron"] - self.game_data["village"]["iron"]
                    self.resman.request(source="research", resource="iron", amount=req)
                    r = False
                if not r:
                    self.logger.debug(
                        "Ignoring research of %s because of resource error (not enough resources) %s", unit_type, str(data["research_error"])
                    )
                    self.logger.debug("Research needs resources")
                else:
                    self.logger.debug(
                        "Ignoring research of %s because of research error %s", unit_type, str(data["research_error"])
                    )
                return False
            if "error_buildings" in data and data["error_buildings"]:
                self.logger.debug(
                    "Ignoring research of %s because of building error %s", unit_type, str(data["error_buildings"])
                )
                return False
            if (
                    "level" in data
                    and "level_highest" in data
                    and data["level_highest"] != 0
                    and data["level"] == data["level_highest"]
            ):
                return False
            res = self.wrapper.get_api_action(
                village_id=self.village_id,
                action="research",
                params={"screen": "smith"},
                data={
                    "tech_id": unit_type,
                    "source": self.village_id,
                    "h": self.wrapper.last_h,
                },
            )
            if res:
                if "research_time" in data:
                    self._research_wait = time.time() + self.research_time(
                        data["research_time"]
                    )
                self.logger.info("Started research of %s", unit_type)
                # self.resman.update(res["game_data"])
                return True
        self.logger.info("Research of %s not yet possible", unit_type)

    def _unlock_gather_options(self, village_data):
        """
        Checks for locked gather options and unlocks them if resources are available.
        """
        if not village_data or 'options' not in village_data:
            return False

        unlocked_something = False
        for option_id in sorted(village_data['options'].keys()):
            option = village_data['options'][option_id]

            # Check if it's locked and has unlock costs specified
            if option.get('is_locked') and option.get('unlock_costs'):
                costs = option['unlock_costs']
                can_afford = True

                # Check if we have enough resources (using self.game_data from update_totals)
                if not self.game_data:
                    self.logger.warning("Cannot check unlock costs, game_data is missing.")
                    return False # Wait for next cycle

                for resource, cost in costs.items():
                    if self.game_data['village'].get(resource, 0) < cost:
                        can_afford = False
                        self.logger.debug(f"Cannot unlock gather option {option_id}: Need {cost} {resource}, have {self.game_data['village'].get(resource, 0)}")
                        # Optionally request resources
                        if self.resman:
                            req = cost - self.game_data['village'].get(resource, 0)
                            self.resman.request(source=f"gather_unlock_{option_id}", resource=resource, amount=req)
                        break

                if can_afford:
                    self.logger.info(f"Attempting to unlock gather option {option_id}...")
                    payload = {
                        "option_id": option_id,
                        "h": self.wrapper.last_h,
                    }
                    # Send API request to unlock
                    api_result = self.wrapper.get_api_action(
                        action="unlock_option",
                        params={"screen": "scavenge_api"},
                        data=payload,
                        village_id=self.village_id,
                    )

                    if api_result and api_result.get("success"):
                        self.logger.info(f"Successfully unlocked gather option {option_id}!")
                        unlocked_something = True
                        # Update game_data to reflect spent resources
                        if 'game_data' in api_result:
                            self.game_data = api_result['game_data']
                            if self.resman:
                                self.resman.update(self.game_data)
                        else:
                            # Manually subtract costs as a fallback
                            for resource, cost in costs.items():
                                self.game_data['village'][resource] -= cost
                    else:
                        self.logger.warning(f"Failed to unlock gather option {option_id}. Result: {api_result}")

        return unlocked_something

    def gather(self, selection=1, disabled_units=None, advanced_gather=True):
        """
        Used for the gather resources functionality where it uses two options:
        - Basic: all troops gather on the selected gather level
        - Advanced: troops are split
        """
        if disabled_units is None:
            disabled_units = []
        if not self.can_gather:
            return False
        url = f"game.php?village={self.village_id}&screen=place&mode=scavenge"
        result = self.wrapper.get_url(url=url)
        village_data = Extractor.village_data(result)

        # --- NEW: Attempt to unlock gather options ---
        if self._unlock_gather_options(village_data):
            # If we unlocked something, refetch the page to get the new state
            self.logger.info("Refetching gather page after unlocking new option.")
            result = self.wrapper.get_url(url=url)
            village_data = Extractor.village_data(result)
        # --- END NEW ---

        sleep = 0
        available_selection = 0

        # --- PERFORMANCE (POINT 2) ---
        # self.troops is already populated by update_totals()
        # Remove redundant request to screen=place&mode=units
        # --- END PERFORMANCE ---

        troops = dict(self.troops)
        self.logger.info(f"Starting gather with self.troops: {self.troops}")
        self.logger.info(f"Local troops copy: {troops}")

        # Use class-level carry capacity but filter for gatherable units
        haul_list = [
            "spear",
            "sword",
            "heavy",
            "axe",
            "light"
        ]
        if "archer" in self.total_troops:
            haul_list.extend(["archer", "marcher"])

        # ADVANCED GATHER: Prioritize highest gathering operations by assigning maximum troops to them first

        if advanced_gather:
            troops = {key: int(value) for key, value in troops.items()}
            self.logger.info(f"Troops after int conversion: {troops}")
            
            # Calculate total carry capacity for logging
            total_carry = 0
            for item in haul_list:
                carry = self.carry_capacity.get(item, 0)
                if item == "knight":
                    continue
                if item in disabled_units:
                    self.logger.debug(f"Skipping {item} - in disabled_units")
                    continue
                if item in troops and int(troops[item]) > 0:
                    carry_contribution = carry * int(troops[item])
                    total_carry += carry_contribution
                    self.logger.debug(f"Unit {item}: {troops[item]} units * {carry} carry = {carry_contribution} total carry")
                else:
                    self.logger.debug(f"Unit {item}: not in troops or count is 0")
            self.logger.info(f"Total carry capacity: {total_carry}")

            # Iterate from highest to lowest operation and assign ALL available troops to each
            for option in list(reversed(sorted(village_data['options'].keys())))[4 - selection:]:
                self.logger.debug(
                    f"Option: {option} Locked? {village_data['options'][option]['is_locked']} Is underway? {village_data['options'][option]['scavenging_squad'] != None}")
                if int(option) <= selection and not village_data['options'][option]['is_locked'] and \
                        village_data['options'][option]['scavenging_squad'] == None:
                    available_selection = int(option)
                    self.logger.info(f"Gather operation {available_selection} is ready to start.")

                    payload = {
                        "squad_requests[0][village_id]": self.village_id,
                        "squad_requests[0][option_id]": str(available_selection),
                        "squad_requests[0][use_premium]": "false",
                    }

                    # Assign ALL available troops to this operation (highest priority)
                    total_carry_for_operation = 0
                    troops_assigned = False
                    
                    for item in haul_list:
                        carry = self.carry_capacity.get(item, 0)
                        if item == "knight":
                            continue
                        if item in disabled_units:
                            continue

                        if item in troops and int(troops[item]) > 0:
                            troops_count = int(troops[item])
                            # Assign all troops of this type to the current operation
                            payload["squad_requests[0][candidate_squad][unit_counts][%s]" % item] = str(troops_count)
                            total_carry_for_operation += carry * troops_count
                            self.logger.debug(f"Assigned {troops_count} {item} to gather operation {available_selection}")
                            # Remove these troops from the pool
                            troops[item] = 0
                            if troops_count > 0:
                                troops_assigned = True
                        else:
                            payload["squad_requests[0][candidate_squad][unit_counts][%s]" % item] = "0"
                    
                    payload["squad_requests[0][candidate_squad][carry_max]"] = str(total_carry_for_operation)
                    
                    if not troops_assigned:
                        self.logger.info(f"No troops available for gather operation {available_selection}, skipping.")
                        continue
                    
                    self.logger.info(f"Sending gather operation {available_selection} with payload: {payload}")
                    payload["h"] = self.wrapper.last_h
                    api_result = self.wrapper.get_api_action(
                        action="send_squads",
                        params={"screen": "scavenge_api"},
                        data=payload,
                        village_id=self.village_id,
                    )
                    self.logger.info(f"Gather operation {available_selection} API result: {api_result}")
                    sleep += random.randint(1, 5)
                    time.sleep(sleep)
                    self.last_gather = int(time.time())
                    self.logger.info(f"Successfully started gather operation {available_selection}")
                else:
                    # Gathering already exists or locked
                    if int(option) <= selection:
                        if village_data['options'][option]['is_locked']:
                            self.logger.info(f"Gather operation {option} is locked, skipping.")
                        elif village_data['options'][option]['scavenging_squad'] != None:
                            self.logger.info(f"Gather operation {option} is already underway, skipping.")
                        else:
                            self.logger.debug(f"Gather operation {option} doesn't meet criteria, skipping.")
                    continue
            # --- OPTIMIZATION ---
            # Persist the remaining troops to the class property so farming logic can use them.
            # Convert back to strings to maintain type consistency
            self.troops = {key: str(value) for key, value in troops.items()}
            # --- END OPTIMIZATION ---

        else:
            for option in reversed(sorted(village_data['options'].keys())):
                self.logger.debug(
                    f"Option: {option} Locked? {village_data['options'][option]['is_locked']} Is underway? {village_data['options'][option]['scavenging_squad'] != None}")
                if int(option) <= selection and not village_data['options'][option]['is_locked'] and \
                        village_data['options'][option]['scavenging_squad'] == None:
                    available_selection = int(option)
                    self.logger.info(f"Gather operation {available_selection} is ready to start.")
                    selection = available_selection

                    payload = {
                        "squad_requests[0][village_id]": self.village_id,
                        "squad_requests[0][option_id]": str(available_selection),
                        "squad_requests[0][use_premium]": "false",
                    }
                    total_carry = 0
                    for item in haul_list:
                        carry = self.carry_capacity.get(item, 0)
                        if item == "knight":
                            continue
                        if item in disabled_units:
                            continue
                        if item in troops and int(troops[item]) > 0:
                            payload[
                                "squad_requests[0][candidate_squad][unit_counts][%s]" % item
                                ] = troops[item]
                            total_carry += carry * int(troops[item])
                            self.logger.debug(f"Assigned {troops[item]} {item} to gather operation {available_selection}")
                        else:
                            payload[
                                "squad_requests[0][candidate_squad][unit_counts][%s]" % item
                                ] = "0"
                    payload["squad_requests[0][candidate_squad][carry_max]"] = str(total_carry)
                    if total_carry > 0:
                        self.logger.info(f"Sending gather operation {available_selection} with payload: {payload}")
                        payload["h"] = self.wrapper.last_h
                        api_result = self.wrapper.get_api_action(
                            action="send_squads",
                            params={"screen": "scavenge_api"},
                            data=payload,
                            village_id=self.village_id,
                        )
                        self.logger.info(f"Gather operation {available_selection} API result: {api_result}")
                        # --- OPTIMIZATION ---
                        # Zero out the troops that were just sent
                        for item in haul_list:
                            if item in self.troops:
                                self.troops[item] = "0"
                        # --- END OPTIMIZATION ---
                        self.last_gather = int(time.time())
                        self.logger.info(f"Successfully started gather operation {selection}")
                    else:
                        self.logger.info(f"No troops available for gather operation {available_selection}, skipping.")
                else:
                    # Gathering already exists or locked
                    if int(option) <= selection:
                        if village_data['options'][option]['is_locked']:
                            self.logger.info(f"Gather operation {option} is locked, skipping.")
                        elif village_data['options'][option]['scavenging_squad'] != None:
                            self.logger.info(f"Gather operation {option} is already underway, skipping.")
                        else:
                            self.logger.debug(f"Gather operation {option} doesn't meet criteria, skipping.")
                    continue
        self.logger.info("All gather operations are underway.")
        return True

    def cancel(self, building, id):
        """
        Cancel a troop recruiting action
        """
        self.wrapper.get_api_action(
            action="cancel",
            params={"screen": building},
            data={"id": id},
            village_id=self.village_id,
        )

    def recruit(self, unit_type, amount=10, wait_for=False, building="barracks"):
        """
        Recruit x amount of x from a certain building
        """
        data = self.wrapper.get_action(action=building, village_id=self.village_id)

        existing = Extractor.active_recruit_queue(data)
        if existing:
            self.logger.info(
                "Building Village %s %s has active recruitment queue, syncing"
                % (self.village_id, building)
            )
            if not self.can_fix_queue:
                self.logger.debug("can_fix_queue is False, not clearing existing queue")
                return True
            for entry in existing:
                self.cancel(building=building, id=entry)
                self.logger.info(
                    "Canceled recruit item %s on building %s" % (entry, building)
                )
            return self.recruit(unit_type, amount, wait_for, building)

        self.recruit_data = Extractor.recruit_data(data)
        self.game_data = Extractor.game_state(data)

        if amount > self.max_batch_size:
            amount = self.max_batch_size

        self.logger.info("Attempting recruitment of %d %s" % (amount, unit_type))

        if unit_type not in self.recruit_data:
            self.logger.warning(
                "Recruitment of %d %s failed because it is not researched"
                % (amount, unit_type)
            )
            self.attempt_research(unit_type)
            return False

        resources = self.recruit_data[unit_type]
        if not resources:
            self.logger.warning(
                "Recruitment of %d %s failed because invalid identifier"
                % (amount, unit_type)
            )
            return False
        if not resources["requirements_met"]:
            self.logger.warning(
                "Recruitment of %d %s failed because it is not researched"
                % (amount, unit_type)
            )
            self.attempt_research(unit_type)
            return False

        get_min = self.get_min_possible(resources)
        if get_min == 0:
            self.logger.info(
                "Recruitment of %d %s failed because of not enough resources"
                % (amount, unit_type)
            )
            self.reserve_resources(resources, amount, get_min, unit_type)
            return False

        needed_reserve = False
        if get_min < amount:
            if wait_for:
                self.logger.warning(
                    "Recruitment of %d %s failed because of not enough resources"
                    % (amount, unit_type)
                )
                self.reserve_resources(resources, amount, get_min, unit_type)
                needed_reserve = True
                return False
            if get_min > 0:
                self.logger.info(
                    "Recruitment of %d %s was set to %d because of resources"
                    % (amount, unit_type, get_min)
                )
                self.reserve_resources(resources, amount, get_min, unit_type)
                amount = get_min
                needed_reserve = True

        if not needed_reserve:
            # No need to reserve resources anymore!
            if f"recruitment_{unit_type}" in self.resman.requested:
                self.resman.requested.pop(f"recruitment_{unit_type}", None)

        result = self.wrapper.get_api_action(
            village_id=self.village_id,
            action="train",
            params={"screen": building, "mode": "train"},
            data={"units[%s]" % unit_type: str(amount)},
        )
        if result is None:
            self.logger.warning(
                "Recruitment of %d %s failed because the server returned no response",
                amount,
                unit_type,
            )
            return False
        if isinstance(result, dict) and "game_data" in result:
            self.resman.update(result["game_data"])
            self.wait_for[self.village_id][building] = int(time.time()) + (
                    amount * int(resources["build_time"])
            )
            # self.troops[unit_type] = str((int(self.troops[unit_type]) if unit_type in self.troops else 0) + amount)
            self.logger.info(
                "Recruitment of %d %s started (%s idle till %d)",
                amount,
                unit_type,
                building,
                self.wait_for[self.village_id][building],
            )
            self.wrapper.reporter.report(
                self.village_id,
                "TWB_RECRUIT",
                "Recruitment of %d %s started (%s idle till %d)"
                % (
                    amount,
                    unit_type,
                    building,
                    self.wait_for[self.village_id][building],
                ),
                )
            return True
        return False

    def reserve_resources(self, resources, wanted_times, has_times, unit_type):
        """
        Reserve resources for a certain recruiting action
        """
        # Resources per unit, batch wanted, batch already recruiting
        create_amount = wanted_times - has_times
        self.logger.debug(f"Requesting resources to recruit %d of %s", create_amount, unit_type)
        for res in ["wood", "stone", "iron"]:
            req = resources[res] * (wanted_times - has_times)
            self.resman.request(source=f"recruitment_{unit_type}", resource=res, amount=req)

    def readable_ts(self, seconds):
        """
        Human readable timestamp
        """
        seconds -= time.time()
        seconds = seconds % (24 * 3600)
        hour = seconds // 3600
        seconds %= 3600
        minutes = seconds // 60
        seconds %= 60

        return "%d:%02d:%02d" % (hour, minutes, seconds)
