"""Utility helpers for parsing Tribal Wars HTML responses."""

import json
import logging
import re
import time
from typing import Any, Dict, List, Literal, Optional


logger = logging.getLogger("Extractor")


_ROW_PATTERN = re.compile(
    r"<tr[^>]*?(?:data-village-id|data-id)\s*=\s*['\"](\d+)['\"][^>]*>(.+?)</tr>",
    re.IGNORECASE | re.DOTALL,
)

_TD_SORT_PATTERN = re.compile(
    r"<td[^>]*data-sort\s*=\s*['\"](\d+)['\"][^>]*>(.*?)</td>",
    re.IGNORECASE | re.DOTALL,
)

_TD_GENERIC_PATTERN = re.compile(r"<td[^>]*>(.*?)</td>", re.IGNORECASE | re.DOTALL)

_COORDS_PATTERN = re.compile(r"\((\d+)\|(\d+)\)")


def _strip_html(value: str) -> str:
    return re.sub(r"<[^>]+>", "", value).strip()


class Extractor:
    """
    Defines various non-compiled regexes for data retrieval
    TODO: use compiled various for CPU efficiency
    """
    @staticmethod
    def village_data(res):
        """
        Detects village data on a page
        """
        if type(res) != str:
            res = res.text
        grabber = re.search(r'var village = (.+);', res)
        if grabber:
            data = grabber.group(1)
            return json.loads(data, strict=False)

    @staticmethod
    def game_state(res):
        """
        Detects the game state that is available on most pages
        """
        if type(res) != str:
            res = res.text
        grabber = re.search(r'TribalWars\.updateGameData\((.+?)\);', res)
        if grabber:
            data = grabber.group(1)
            return json.loads(data, strict=False)

    @staticmethod
    def building_data(res):
        """
        Fetches building data from the main building
        """
        if type(res) != str:
            res = res.text
        dre = re.search(r'(?s)BuildingMain.buildings = (\{.+?\});', res)
        if dre:
            return json.loads(dre.group(1), strict=False)

        # Log diagnostic information when extraction fails
        logger = logging.getLogger("Extractor")
        logger.debug("Failed to extract building data - regex pattern did not match")
        logger.debug(f"Response length: {len(res)} characters")
        
        # Check if we're on the right page
        if 'screen=main' in res:
            logger.debug("Confirmed on main screen page")
        else:
            logger.warning("Not on main screen page - check page navigation")
        
        # Save HTML for debugging if extraction fails
        try:
            import os
            debug_dir = "cache/logs"
            os.makedirs(debug_dir, exist_ok=True)
            debug_file = os.path.join(debug_dir, f"building_extract_fail_{int(time.time())}.html")
            with open(debug_file, 'w', encoding='utf-8') as f:
                f.write(res)
            logger.debug(f"Saved failed extraction HTML to: {debug_file}")
        except Exception as e:
            logger.debug(f"Could not save debug HTML: {e}")
        
        return None

    @staticmethod
    def get_quests(res):
        """
        Gets quest data on almost any page
        """
        if type(res) != str:
            res = res.text
        get_quests = re.search(r'Quests.setQuestData\((\{.+?\})\);', res)
        if get_quests:
            result = json.loads(get_quests.group(1), strict=False)
            for quest in result:
                data = result[quest]
                if data['goals_completed'] == data['goals_total']:
                    return quest
        return None

    @staticmethod
    def get_quest_rewards(res):
        """
        Detects if there are rewards available for quests
        """
        if type(res) != str:
            res = res.text
        get_rewards = re.search(r'RewardSystem\.setRewards\(\s*(\[\{.+?\}\]),', res)
        rewards = []
        if get_rewards:
            result = json.loads(get_rewards.group(1), strict=False)
            for reward in result:
                if reward['status'] == "unlocked":
                    rewards.append(reward)
        # Return all off them
        return rewards

    @staticmethod
    def map_data(res):
        """
        Detects other villages on the map page
        """
        if type(res) != str:
            res = res.text
        data = re.search(r'(?s)TWMap.sectorPrefech = (\[(.+?)\]);', res)
        if data:
            result = json.loads(data.group(1), strict=False)
            return result

    @staticmethod
    def smith_data(res):
        """
        Gets smith data
        """
        if type(res) != str:
            res = res.text
        data = re.search(r'(?s)BuildingSmith.techs = (\{.+?\});', res)
        if data:
            result = json.loads(data.group(1), strict=False)
            return result
        return None

    @staticmethod
    def premium_data(res):
        """
        Detects data on the premium exchange page
        """
        if type(res) != str:
            res = res.text
        data = re.search(r'(?s)PremiumExchange.receiveData\((.+?)\);', res)
        if data:
            result = json.loads(data.group(1), strict=False)
            return result
        return None

    @staticmethod
    def recruit_data(res):
        """
        Fetches recruit data for the current building
        """
        if type(res) != str:
            res = res.text
        data = re.search(r'(?s)unit_managers.units = (\{.+?\});', res)
        if data:
            raw = data.group(1)
            quote_keys_regex = r'([\{\s,])(\w+)(:)'
            processed = re.sub(quote_keys_regex, r'\1"\2"\3', raw)
            result = json.loads(processed, strict=False)
            return result

    @staticmethod
    def units_in_village(res):
        """
        Detects all units in the village
        """
        if type(res) != str:
            res = res.text
        matches = re.search(r'<table id="units_home".*?</tr>(.*?)</tr>', res, re.DOTALL)
        # We get the start of the table and grab the 2nd row (Where "From this village" troops are located)
        if matches:
            table_content = matches.group(1)
            unit_matches = re.findall(r'class=\'unit-item unit-item-(.*?)\'[^>]*>(\d+)</td>', table_content)
            # Find all the tuples (name, quantity) under the class "unit-item unit-item-*troop_name*"
            units = [(re.sub(r'\s*tooltip\s*', '', unit_name), unit_quantity) for unit_name, unit_quantity in
                     unit_matches if int(unit_quantity) > 0]
            # Filter units with quantity = 0, also for the Paladin,
            # the name would be "knight tooltip", so we had to remove that.
            return units
        return []

    @staticmethod
    def active_building_queue(res):
        """
        Detects queued building entries
        """
        if type(res) != str:
            res = res.text
        builder = re.search('(?s)<table id="build_queue"(.+?)</table>', res)
        if not builder:
            return 0

        return builder.group(1).count('<a class="btn btn-cancel"')

    @staticmethod
    def active_recruit_queue(res):
        """
        Detects active recruitment entries
        """
        if type(res) != str:
            res = res.text
        builder = re.findall(r'(?s)TrainOverview\.cancelOrder\((\d+)\)', res)
        return builder

    @staticmethod
    def village_ids_from_game_data(res) -> List[str]:
        """
        Extracts village IDs from the TribalWars.updateGameData JSON.
        This is a fallback method when quickedit-vn elements are not present
        (e.g., when the server returns 'overview' instead of 'overview_villages').

        For multi-village accounts, this extracts all village IDs from the
        game_data["villages"] mapping when available.
        """
        if not isinstance(res, str):
            res = res.text

        # Extract the game data JSON
        game_data = Extractor.game_state(res)
        if not game_data:
            return []

        village_ids = []

        # Method 1: Try to get all villages from the villages mapping (multi-village accounts)
        # The game_data JSON contains a "villages" object with all owned villages
        if "villages" in game_data and isinstance(game_data["villages"], dict):
            # Villages mapping contains village_id as keys
            village_ids.extend([str(vid) for vid in game_data["villages"].keys()])

        # Method 2: Fallback to current village ID if no villages mapping exists
        # This handles edge cases and single-village accounts
        if not village_ids and "village" in game_data and "id" in game_data["village"]:
            village_id = str(game_data["village"]["id"])
            village_ids.append(village_id)

        return village_ids

    @staticmethod
    def village_ids_from_overview(res) -> List[str]:
        """
        Fetches villages from the overview page.
        Uses quickedit-vn elements as primary method with game_data JSON as fallback.
        """
        if not isinstance(res, str):
            res = res.text

        # Primary method: Look for quickedit-vn elements (works on overview_villages page)
        # Use two patterns to handle both attribute orders
        pattern1 = re.compile(
            r'<[a-zA-Z0-9]+\s+[^>]*?class=["\']([^"\']*\bquickedit-vn\b[^"\']*)["\'][^>]*?data-id=["\'](\d+)["\']',
            re.IGNORECASE
        )
        pattern2 = re.compile(
            r'<[a-zA-Z0-9]+\s+[^>]*?data-id=["\'](\d+)["\'][^>]*?class=["\']([^"\']*\bquickedit-vn\b[^"\']*)["\']',
            re.IGNORECASE
        )

        # Find all matches with their positions to preserve order
        all_matches = []

        for match in pattern1.finditer(res):
            all_matches.append((match.start(), match.group(2)))  # (position, id)

        for match in pattern2.finditer(res):
            all_matches.append((match.start(), match.group(1)))  # (position, id)

        # Sort by position and extract IDs, then deduplicate while preserving order
        all_matches.sort(key=lambda x: x[0])
        village_ids = list(dict.fromkeys([id for pos, id in all_matches]))

        # Fallback: If no villages found via quickedit-vn, try game_data JSON
        # This handles cases where server returns 'overview' instead of 'overview_villages'
        if not village_ids:
            village_ids = Extractor.village_ids_from_game_data(res)

        return village_ids

    @staticmethod
    def overview_production_data(res) -> List[Dict[str, Any]]:
        """Parse the production overview page and return per-village data.

        Returns a list of dictionaries with keys:
        ``id``, ``name``, ``x``, ``y``, ``points``, ``wood``, ``stone``, ``iron``, ``storage``.
        Missing values are returned as zero.
        """

        if not isinstance(res, str):
            res = res.text

        def _to_int(value: Optional[str]) -> int:
            if not value:
                return 0
            cleaned = re.sub(r"[^0-9]", "", value)
            return int(cleaned) if cleaned else 0

        def _extract_coords(text: str) -> Optional[Dict[str, int]]:
            match = _COORDS_PATTERN.search(text)
            if not match:
                return None
            return {"x": int(match.group(1)), "y": int(match.group(2))}

        def _extract_sort(row: str, keywords) -> Optional[int]:
            if isinstance(keywords, str):
                patterns = [re.compile(re.escape(keywords), re.IGNORECASE | re.DOTALL)]
            else:
                patterns = [
                    re.compile(re.escape(keyword), re.IGNORECASE | re.DOTALL)
                    for keyword in keywords
                ]
            for sort_value, cell_html in _TD_SORT_PATTERN.findall(row):
                if any(pattern.search(cell_html) for pattern in patterns):
                    return int(sort_value)
            return None

        data = []
        for village_id, row_html in _ROW_PATTERN.findall(res):
            # Extract display name
            name_match = re.search(
                r"class=\"quickedit-label\"[^>]*>(.*?)</",
                row_html,
                re.IGNORECASE | re.DOTALL,
            )
            name_raw = name_match.group(1) if name_match else row_html
            name = _strip_html(name_raw)

            coords = _extract_coords(row_html) or _extract_coords(name)
            points = _extract_sort(row_html, "icon header points")
            wood = _extract_sort(row_html, "icon header wood")
            stone = _extract_sort(row_html, ["icon header stone", "icon header clay"])
            iron = _extract_sort(row_html, "icon header iron")
            storage = _extract_sort(row_html, ["icon header storage", "icon header warehouse"])

            fallback_used = False
            if wood is None or stone is None or iron is None or storage is None:
                # Fallback: derive from numeric columns order after name/points
                cells = _TD_GENERIC_PATTERN.findall(row_html)
                numeric_values = []
                for cell in cells:
                    text = _strip_html(cell)
                    value = _to_int(text)
                    if value:
                        numeric_values.append(value)
                # Typical order: points, wood, stone, iron, storage, ...
                if wood is None and len(numeric_values) >= 2:
                    wood = numeric_values[1]
                    fallback_used = True
                if stone is None and len(numeric_values) >= 3:
                    stone = numeric_values[2]
                    fallback_used = True
                if iron is None and len(numeric_values) >= 4:
                    iron = numeric_values[3]
                    fallback_used = True
                if storage is None and len(numeric_values) >= 5:
                    storage = numeric_values[4]
                    fallback_used = True
                if points is None and numeric_values:
                    points = numeric_values[0]
                    fallback_used = True

            if fallback_used:
                logger.debug("overview_production_data fallback parsing used for village %s", village_id)

            entry = {
                "id": village_id,
                "name": name,
                "x": coords["x"] if coords else 0,
                "y": coords["y"] if coords else 0,
                "points": points or 0,
                "wood": wood or 0,
                "stone": stone or 0,
                "iron": iron or 0,
                "storage": storage or 0,
            }
            data.append(entry)

        return data

    @staticmethod
    def overview_trader_data(res, overview_type: Literal['own', 'inc'] = 'own') -> Dict[str, Dict[str, int]]:
        """Parse trader overview data.

        Args:
            res: HTML response text or object with ``text`` attribute.
            overview_type: ``'own'`` for merchant availability or ``'inc'`` for incoming resources.

        Returns:
            Mapping of village_id to a dictionary containing parsed values.
        """

        if overview_type not in ('own', 'inc'):
            raise ValueError("overview_type must be 'own' or 'inc'")

        if not isinstance(res, str):
            res = res.text

        data: Dict[str, Dict[str, int]] = {}

        def _extract_icon_value(row_html: str, resources) -> int:
            if isinstance(resources, str):
                patterns = [re.compile(rf"icon\s+header\s+{re.escape(resources)}", re.IGNORECASE)]
            else:
                patterns = [
                    re.compile(rf"icon\s+header\s+{re.escape(resource)}", re.IGNORECASE)
                    for resource in resources
                ]
            for cell_html in _TD_GENERIC_PATTERN.findall(row_html):
                if any(pattern.search(cell_html) for pattern in patterns):
                    text = re.sub(r"<[^>]+>", "", cell_html)
                    cleaned = re.sub(r"[^0-9]", "", text)
                    return int(cleaned) if cleaned else 0
            return 0

        for village_id, row_html in _ROW_PATTERN.findall(res):
            if overview_type == 'own':
                # merchants availability typically shown as a/b in the row
                merchants_match = re.search(
                    r"(\d+)\s*/\s*(\d+)",
                    row_html,
                )
                if merchants_match:
                    merchants_avail = int(merchants_match.group(1))
                    merchants_total = int(merchants_match.group(2))
                else:
                    merchants_avail = merchants_total = 0
                data[village_id] = {
                    "merchants_avail": merchants_avail,
                    "merchants_total": merchants_total,
                }
            else:
                data[village_id] = {
                    "incoming_wood": _extract_icon_value(row_html, 'wood'),
                    "incoming_stone": _extract_icon_value(row_html, ['stone', 'clay']),
                    "incoming_iron": _extract_icon_value(row_html, 'iron'),
                }

        return data

    @staticmethod
    def units_in_total(res):
        """
        Gets total amount of units in a village
        """
        if type(res) != str:
            res = res.text
        # hide units from other villages
        res = re.sub(r'(?s)<span class="village_anchor.+?</tr>', '', res)
        
        results = []
        # Find all unit cells
        # We match the entire <td> to gracefully pull data-unit-count or fallback to text
        cells = re.findall(r'(<td[^>]*class=[\'"][^\'"]*\bunit-item-([a-z]+)\b[^\'"]*[\'"][^>]*>.*?</td>)', res, re.IGNORECASE | re.DOTALL)
        
        for cell_html, unit_type in cells:
            # Prefer data-unit-count
            count_match = re.search(r'data-unit-count=["\'](\d+)["\']', cell_html)
            if count_match:
                results.append((unit_type, count_match.group(1)))
            else:
                # Fallback to text inside td, stripping tags and dots
                text = re.sub(r'<[^>]+>', '', cell_html)
                cleaned = re.sub(r'[^\d]', '', text)
                if cleaned:
                    results.append((unit_type, cleaned))
                else:
                    results.append((unit_type, '0'))
                    
        return results

    @staticmethod
    def get_farm_bag_state(res):
        """Extracts current and maximum farm bag values from the place screen."""
        if isinstance(res, str):
            html = res
        else:
            html = res.text

        text = re.sub(r'<span class="grey">\.</span>', '.', html, flags=re.IGNORECASE)
        text = re.sub(r'<[^>]+>', ' ', text)

        matches = []
        # First try language specific anchor (German-only wording on DE servers)
        # This keeps backwards compatibility with existing cache data; see README for locale caveats.
        lang_match = re.findall(
            r'Erbeutete\s+Rohstoffe[^\d]*(\d[\d\.\,]*)\s*/\s*(\d[\d\.\,]*)',
            text,
            re.IGNORECASE,
        )
        matches.extend(lang_match)

        if not matches:
            # fallback to generic pattern capturing ratio around slash
            fallback = re.findall(
                r'(\d[\d\.\,]*)\s*/\s*(\d[\d\.\,]*)',
                text,
            )
            matches.extend(fallback)

        def _to_int(value):
            return int(value.replace('.', '').replace(',', '').strip())

        parsed = []
        for current, maximum in matches:
            try:
                parsed.append((_to_int(current), _to_int(maximum)))
            except ValueError:
                continue

        if not parsed:
            return None

        current, maximum = max(parsed, key=lambda item: item[0])
        if maximum <= 0:
            return None
        return {"current": current, "max": maximum}

    @staticmethod
    def attack_form(res):
        """
        Detects input fiels in the attack form
        ... because there are many :)
        """
        if type(res) != str:
            res = res.text
        data = re.findall(r'(?s)<input.+?name="(.+?)".+?value="(.*?)"', res)
        return data

    @staticmethod
    def attack_duration(res):
        """
        Detects the duration of an attack
        """
        if type(res) != str:
            res = res.text
        data = re.search(r'<span class="relative_time" data-duration="(\d+)"', res)
        if data:
            return int(data.group(1))
        return 0

    @staticmethod
    def report_table(res):
        """
        Fetches information from a report
        """
        if type(res) != str:
            res = res.text
        data = re.findall(r'(?s)class="report-link" data-id="(\d+)"', res)
        return data

    @staticmethod
    def get_daily_reward(res):
        """
        Detects if there are unopened daily rewards
        """
        if type(res) != str:
            res = res.text
        get_daily = re.search(r'DailyBonus.init\((\s+\{.*\}),', res)
        if not get_daily:
            return None

        try:
            data = json.loads(get_daily.group(1), strict=False)
        except json.JSONDecodeError:
            return None

        reward_count_unlocked = data.get("reward_count_unlocked")
        if reward_count_unlocked is None:
            return None

        reward_key = str(reward_count_unlocked)
        chests = data.get("chests", {})
        if isinstance(chests, dict):
            chest = chests.get(reward_key)
            if isinstance(chest, dict) and chest.get("is_collected"):
                return reward_key
        return None
