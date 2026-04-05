import logging
import time
import random
import re
from math import ceil
from dataclasses import dataclass
from typing import Dict, List, Optional
from bs4 import BeautifulSoup

@dataclass
class ScavengeLevel:
    level_id: int
    capacity: int          # maks. surowce do zebrania
    duration_seconds: int  # czas podróży w sekundach
    is_locked: bool
    is_running: bool

@dataclass
class ScavengeAssignment:
    level_id: int
    units: dict  # {"sword": N, "spear": N, ...}

class ScavengingUnavailableError(Exception):
    """Raised when scavenging is not available for the village."""
    pass

class ScavengingManager:
    """
    Zarządza automatycznym zbieractwem dla jednej wioski.
    Pobiera dane z gry przez HTTP (ciasteczka z core/), parsuje
    dostępne poziomy zbieractwa i optymalnie rozdziela jednostki
    defensywne pomiędzy poziomami, maksymalizując surowce/h.
    """

    UNIT_CARRY = {
        "spear":   25,
        "sword":   15,
        "axe":     10,
        "archer":  10,
        "light":   80,   # LK — zarezerwowana, nie używana
        "marcher": 50,  # zarezerwowana, nie używana
        "heavy":   50,
        "ram":      0,
        "catapult": 0,
        "knight":  100,
        "snob":     0,
    }

    def __init__(self, village_id: int, config: dict, wrapper):
        """
        Initialize ScavengingManager.
        
        :param village_id: ID wioski (int) z config["villages"]
        :param config: słownik village_template z config.json
        :param wrapper: instancja istniejącego HTTP wrappera z core/
        """
        self.village_id = village_id
        self.config = config
        self.wrapper = wrapper
        self.logger = logging.getLogger(__name__)
        self.last_run = 0

    def fetch_scavenge_page(self) -> BeautifulSoup:
        """
        Pobiera stronę: https://{server}/game.php?village={village_id}&screen=place&mode=scavenge
        Używa wrapper.get(url) - w tym przypadku get_url z WebWrapper
        Parsuje HTML przez BeautifulSoup(response.text, "html.parser")
        Rzuca ScavengingUnavailableError jeśli zakładka jest niedostępna
        """
        url = f"game.php?village={self.village_id}&screen=place&mode=scavenge"
        response = self.wrapper.get_url(url)
        if not response or response.status_code != 200 or "screen=place" not in response.url:
            raise ScavengingUnavailableError(f"Scavenge page not available for village {self.village_id}")
        
        soup = BeautifulSoup(response.text, "html.parser")
        # Check if the scavenge options are present
        if not soup.select_one(".scavenge-option"):
            raise ScavengingUnavailableError(f"Scavenging not unlocked or not available in village {self.village_id}")
            
        return soup

    def parse_available_units(self, soup: BeautifulSoup) -> Dict[str, int]:
        """
        Wyciąga aktualnie dostępne (nie w drodze) jednostki wioski ze strony zbieractwa
        Format zwracany: {"sword": 450, "spear": 300, "axe": 200, ...}
        Pomija jednostki z gather_reserve_for_farm (LK, marcher — 100% zarezerwowane)
        Pomija jednostki nieobecne w gather_unit_priority
        """
        units = {}
        priority_units = self.config.get("gather_unit_priority", ["sword", "spear", "axe"])
        reserve_cfg = self.config.get("gather_reserve_for_farm", {"light": 1.0, "marcher": 1.0})

        # Units are usually in spans with class "units-entry-all" and data-unit attribute
        unit_elements = soup.select(".units-entry-all")
        for el in unit_elements:
            unit_name = el.get("data-unit")
            if not unit_name:
                continue
            
            if unit_name not in priority_units:
                continue

            try:
                # Text is usually "(123)"
                count_text = el.text.strip("() ")
                count = int(count_text)
            except (ValueError, TypeError):
                continue

            if count <= 0:
                continue

            reserve_ratio = reserve_cfg.get(unit_name, 0.0)
            available = int(count * (1.0 - reserve_ratio))
            
            if available > 0:
                units[unit_name] = available

        return units

    def parse_scavenge_levels(self, soup: BeautifulSoup) -> List[ScavengeLevel]:
        """
        Wyciąga dostępne poziomy zbieractwa z HTML
        Zwraca listę ScavengeLevel(level_id, capacity, duration_seconds, is_locked, is_running)
        Filtruje do poziomów z gather_levels (domyślnie [1,2,3])
        Pomija poziomy, które już trwają (is_running=True)
        """
        levels = []
        enabled_levels = self.config.get("gather_levels", [1, 2, 3])
        
        options = soup.select(".scavenge-option")
        for opt in options:
            # Level ID is usually in a data-id or similar, or extracted from button
            # But more reliably from the "data-option-id" of the button if available
            btn = opt.select_one(".free_send_button")
            
            # If button is missing, it might be running or locked
            is_running = bool(opt.select_one(".timer"))
            is_locked = bool(opt.select_one(".lock"))
            
            # Try to get level_id from data-option-id if button exists, or from script/text
            level_id = None
            if btn:
                level_id = int(btn.get("data-option-id"))
            else:
                # If running, the level ID might be in some other attribute
                # Let's try to find it in the opt class or sibling
                # Usually it's in the structure of the options
                # Fallback: parse from text if possible or use order
                pass
            
            # If still None, we might need a regex on the option content
            if level_id is None:
                match = re.search(r'ScavengeWidgets\.sendSquads\((\d+)', opt.decode_contents())
                if match:
                    level_id = int(match.group(1))

            if level_id is None or level_id not in enabled_levels:
                continue
            
            if is_running or is_locked:
                continue

            # Capacity: "Zdolność łupu: 1.234"
            capacity = 0
            cap_el = opt.select_one(".status-specific")
            if cap_el:
                cap_match = re.search(r'(\d+)', cap_el.text.replace(".", ""))
                if cap_match:
                    capacity = int(cap_match.group(1))

            levels.append(ScavengeLevel(
                level_id=level_id,
                capacity=capacity,
                duration_seconds=0, # Not used in greedy split
                is_locked=is_locked,
                is_running=is_running
            ))
            
        return levels

    def calculate_optimal_split(self, units: Dict[str, int], levels: List[ScavengeLevel]) -> List[ScavengeAssignment]:
        """
        Algorytm optymalnego podziału wojsk.
        1. Policz łączną nośność dostępnych jednostek.
        2. Posortuj poziomy malejąco po capacity.
        3. Przydziel jednostki zachłannie.
        4. Wypełnij do gather_min_fill_ratio * capacity.
        """
        if not units or not levels:
            return []

        total_carry = sum(count * self.UNIT_CARRY.get(u, 0) for u, count in units.items())
        total_units = sum(units.values())
        if total_units == 0:
            return []
        
        avg_carry_per_unit = total_carry / total_units

        # Sort levels descending by capacity
        sorted_levels = sorted(levels, key=lambda x: x.capacity, reverse=True)
        
        min_fill_ratio = self.config.get("gather_min_fill_ratio", 0.85)
        assignments = []
        
        remaining_units = {k: v for k, v in units.items()}
        
        for level in sorted_levels:
            current_total_units = sum(remaining_units.values())
            if current_total_units == 0:
                break
                
            current_total_carry = sum(count * self.UNIT_CARRY.get(u, 0) for u, count in remaining_units.items())
            
            # Required carry for this level to meet min_fill_ratio
            required_carry = level.capacity * min_fill_ratio
            
            if current_total_carry < required_carry:
                continue
                
            # How many units needed to reach 100% capacity (ideally)
            # or as much as we have if it's > min_fill_ratio
            units_needed = ceil(level.capacity / avg_carry_per_unit)
            
            # If we don't have enough units to fill 100%, we take all we have
            # (since we already checked it's at least min_fill_ratio)
            to_take_total = min(units_needed, current_total_units)
            
            # Distribute taking units proportionally from what's left
            level_units = {}
            ratio = to_take_total / current_total_units
            
            taken_so_far = 0
            for u, count in remaining_units.items():
                take = int(count * ratio)
                if take > 0:
                    level_units[u] = take
                    remaining_units[u] -= take
                    taken_so_far += take
            
            # Correction for rounding
            if taken_so_far < to_take_total:
                diff = to_take_total - taken_so_far
                for u in remaining_units:
                    if remaining_units[u] >= diff:
                        level_units[u] = level_units.get(u, 0) + diff
                        remaining_units[u] -= diff
                        break
            
            if level_units:
                assignments.append(ScavengeAssignment(level_id=level.level_id, units=level_units))

        return assignments

    def send_scavenge(self, assignment: ScavengeAssignment) -> bool:
        """
        Wysyła POST do gry dla danego poziomu zbieractwa
        """
        # Payload format for scavenge
        payload = {
            "squad_requests[0][village_id]": str(self.village_id),
            "squad_requests[0][option_id]": str(assignment.level_id),
            "squad_requests[0][use_premium]": "false",
            "h": self.wrapper.last_h
        }
        
        total_carry = 0
        for unit, count in assignment.units.items():
            payload[f"squad_requests[0][candidate_squad][unit_counts][{unit}]"] = str(count)
            total_carry += count * self.UNIT_CARRY.get(unit, 0)
        
        payload["squad_requests[0][candidate_squad][carry_max]"] = str(total_carry)

        self.logger.info(f"Sending scavenge for village {self.village_id}, level {assignment.level_id}")
        
        # Action is usually "send_squads" on screen "scavenge_api"
        res = self.wrapper.post_api_data(
            village_id=self.village_id,
            action="send_squads",
            params={"screen": "scavenge_api"},
            data=payload
        )
        
        if res and (res == True or (isinstance(res, dict) and res.get("success"))):
            return True
            
        self.logger.error(f"Failed to send scavenge for village {self.village_id}: {res}")
        return False

    def run(self) -> None:
        """
        Główna pętla wywoływana przez schedulera bota
        """
        if not self.config.get("gather_enabled", False):
            return

        cooldown_mins = self.config.get("gather_cooldown_minutes", 5)
        if time.time() - self.last_run < cooldown_mins * 60:
            return

        self.last_run = time.time()

        try:
            soup = self.fetch_scavenge_page()
            units = self.parse_available_units(soup)
            if not units:
                return

            levels = self.parse_scavenge_levels(soup)
            if not levels:
                return

            assignments = self.calculate_optimal_split(units, levels)
            for assign in assignments:
                if self.send_scavenge(assign):
                    # Sleep a bit between levels
                    time.sleep(random.uniform(1.0, 3.0))
                    
        except ScavengingUnavailableError as e:
            self.logger.warning(f"Scavenging unavailable for village {self.village_id}: {e}")
        except Exception as e:
            self.logger.exception(f"Error in ScavengingManager for village {self.village_id}: {e}")
