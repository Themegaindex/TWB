import logging
import random
import time
from core.extractors import Extractor

class GatherMixin:
    def _unlock_gather_options(self, village_data):
        if not village_data or 'options' not in village_data:
            return False

        unlocked_something = False
        for option_id in sorted(village_data['options'].keys()):
            option = village_data['options'][option_id]
            if option.get('is_locked') and option.get('unlock_costs'):
                costs = option['unlock_costs']
                can_afford = True
                if not self.game_data:
                    return False

                for resource, cost in costs.items():
                    if self.game_data['village'].get(resource, 0) < cost:
                        can_afford = False
                        if self.resman:
                            req = cost - self.game_data['village'].get(resource, 0)
                            self.resman.request(source=f"gather_unlock_{option_id}", resource=resource, amount=req)
                        break

                if can_afford:
                    api_result = self.wrapper.get_api_action(
                        action="unlock_option",
                        params={"screen": "scavenge_api"},
                        data={"option_id": option_id, "h": self.wrapper.last_h},
                        village_id=self.village_id,
                    )
                    if api_result and api_result.get("success"):
                        unlocked_something = True
                        if 'game_data' in api_result:
                            self.game_data = api_result['game_data']
                            if self.resman:
                                self.resman.update(self.game_data)
        return unlocked_something

    def gather(self, selection=1, disabled_units=None, advanced_gather=True):
        if disabled_units is None:
            disabled_units = []
        if not self.can_gather:
            return False
        url = f"game.php?village={self.village_id}&screen=place&mode=scavenge"
        result = self.wrapper.get_url(url=url)
        village_data = Extractor.village_data(result)

        if self._unlock_gather_options(village_data):
            result = self.wrapper.get_url(url=url)
            village_data = Extractor.village_data(result)

        troops = {k: int(v) for k, v in self.troops.items()}
        haul_list = ["spear", "sword", "heavy", "axe", "light"]
        if "archer" in self.total_troops:
            haul_list.extend(["archer", "marcher"])

        if advanced_gather:
            for option in list(reversed(sorted(village_data['options'].keys())))[4 - selection:]:
                if int(option) <= selection and not village_data['options'][option]['is_locked'] and village_data['options'][option]['scavenging_squad'] is None:
                    payload = {"squad_requests[0][village_id]": self.village_id, "squad_requests[0][option_id]": str(option), "squad_requests[0][use_premium]": "false"}
                    total_carry_for_operation = 0
                    troops_assigned = False
                    for item in haul_list:
                        if item in disabled_units or item not in troops or troops[item] <= 0:
                            payload["squad_requests[0][candidate_squad][unit_counts][%s]" % item] = "0"
                            continue
                        count = troops[item]
                        payload["squad_requests[0][candidate_squad][unit_counts][%s]" % item] = str(count)
                        total_carry_for_operation += self.carry_capacity.get(item, 0) * count
                        troops[item] = 0
                        troops_assigned = True
                    payload["squad_requests[0][candidate_squad][carry_max]"] = str(total_carry_for_operation)
                    if troops_assigned:
                        payload["h"] = self.wrapper.last_h
                        self.wrapper.get_api_action(action="send_squads", params={"screen": "scavenge_api"}, data=payload, village_id=self.village_id)
                        time.sleep(random.uniform(1, 4))
            self.troops = {k: str(v) for k, v in troops.items()}
        else:
            for option in reversed(sorted(village_data['options'].keys())):
                if int(option) <= selection and not village_data['options'][option]['is_locked'] and village_data['options'][option]['scavenging_squad'] is None:
                    payload = {"squad_requests[0][village_id]": self.village_id, "squad_requests[0][option_id]": str(option), "squad_requests[0][use_premium]": "false"}
                    total_carry = 0
                    for item in haul_list:
                        if item in disabled_units or item not in self.troops or int(self.troops[item]) <= 0:
                            payload["squad_requests[0][candidate_squad][unit_counts][%s]" % item] = "0"
                            continue
                        count = int(self.troops[item])
                        payload["squad_requests[0][candidate_squad][unit_counts][%s]" % item] = str(count)
                        total_carry += self.carry_capacity.get(item, 0) * count
                    payload["squad_requests[0][candidate_squad][carry_max]"] = str(total_carry)
                    if total_carry > 0:
                        payload["h"] = self.wrapper.last_h
                        self.wrapper.get_api_action(action="send_squads", params={"screen": "scavenge_api"}, data=payload, village_id=self.village_id)
                        for item in haul_list:
                            if item in self.troops: self.troops[item] = "0"
                        break
        return True
