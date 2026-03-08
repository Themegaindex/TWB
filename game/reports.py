"""
Report management
"""
import json
import logging
import re
from datetime import datetime

from core.extractors import Extractor
from core.filemanager import FileManager
# --- PERFORMANCE (POINT 3) ---
from game.attack import AttackCache
# --- END PERFORMANCE ---

try:
    from core.database import DatabaseManager
    _DB_AVAILABLE = True
except Exception:
    _DB_AVAILABLE = False


class ReportManager:
    """
    Class to "efficiently" manage reports
    """
    wrapper = None
    village_id = None
    game_state = None
    logger = None
    last_reports = {}

    def __init__(self, wrapper=None, village_id=None):
        """
        Creates the report manager
        """
        self.wrapper = wrapper
        self.village_id = village_id

    def has_resources_left(self, vid):
        """
        Checks if there are any resources left after farm
        Used by the farm manager script
        """
        possible_reports = []
        for repid in self.last_reports:
            entry = self.last_reports[repid]
            if vid == entry["dest"] and entry["extra"].get("when", None):
                possible_reports.append(entry)
        # self.logger.debug(f"Considered {len(possible_reports)} reports")
        if len(possible_reports) == 0:
            return False, {}

        def highest_when(attack):
            """
            Converts the date of an attack when resource gains were high
            """
            return datetime.fromtimestamp(int(attack["extra"]["when"]))

        entry = max(possible_reports, key=highest_when)
        self.logger.debug("This is the newest? %s", datetime.fromtimestamp(int(entry["extra"]["when"])))
        if entry["extra"].get("resources", None):
            return True, entry["extra"]["resources"]
        return False, {}

    def safe_to_engage(self, vid):
        """
        Calculates if a village is safe to engage without custom interaction
        Just sending a 0 losses attack overrides this behaviour
        """
        for repid in self.last_reports:
            entry = self.last_reports[repid]
            if vid == entry["dest"]:
                if entry["type"] == "attack" and entry["losses"] == {}:
                    return 1
                if (
                        entry["type"] == "scout"
                        and entry["losses"] == {}
                        and (
                        entry["extra"]["defence_units"] == {}
                        or entry["extra"]["defence_units"]
                        == entry["extra"]["defence_losses"]
                )
                ):
                    return 1

                if entry["losses"] != {}:
                    # Disengage if anything was lost!
                    return 0
        return -1

    # --- PERFORMANCE (POINT 2) ---
    def read(self, page=0, full_run=False, overview_html=None):
        """
        Read some (or all if you like) reports
        Uses cached overview_html for page 0
        """
        # --- END PERFORMANCE ---
        if not self.logger:
            self.logger = logging.getLogger("Reports")

        if len(self.last_reports) == 0:
            self.logger.info("First run, re-reading cache entries")
            self.last_reports = ReportCache.cache_grab()
            self.logger.info("Got %d reports from cache", len(self.last_reports))

        ids = []
        # --- PERFORMANCE (POINT 2) ---
        if page == 0 and overview_html:
            self.logger.debug("Reading reports from cached overview_html")
            self.game_state = Extractor.game_state(overview_html)
            ids = Extractor.report_table(overview_html)
        else:
            # Fetch subsequent pages normally
            offset = page * 12
            url = f"game.php?village={self.village_id}&screen=report&mode=all"
            if page > 0:
                url += f"&from={offset}"
            result = self.wrapper.get_url(url)
            self.game_state = Extractor.game_state(result)
            ids = Extractor.report_table(result)
        # --- END PERFORMANCE ---

        new = 0
        from core.database import DatabaseManager

        for report_id in ids:
            if report_id in self.last_reports:
                continue
                
            # Optionally check database if report exists to prevent redundant downloads
            try:
                if getattr(DatabaseManager, 'get_report', None):
                    if DatabaseManager.get_report(report_id):
                        self.last_reports[report_id] = True
                        continue
            except Exception:
                pass

            new += 1
            url = f"game.php?village={self.village_id}&screen=report&mode=all&group_id=0&view={report_id}"
            data = self.wrapper.get_url(url)

            get_type = re.search(r'class="report_(\w+)', data.text)
            if get_type:
                report_type = get_type.group(1)
                if report_type == "ReportAttack":
                    self.attack_report(data.text, report_id)
                    continue

                else:
                    res = self.put(report_id, report_type=report_type)
                    self.last_reports[report_id] = res
        if new == 12 or (full_run and page < 20):
            page += 1
            self.logger.debug(
                "%d new reports where added, also checking page %d", new, page
            )
            return self.read(page, full_run=full_run)
        return None

    def re_unit(self, inp):
        """
        No idea why I made this and what it does
        Guessing reading a line of units?
        """
        output = {}
        for row in inp:
            k, v = row
            if int(v) > 0:
                output[k] = int(v)
        return output

    def re_building(self, inp):
        """
        Read building levels from a report entry
        """
        output = {}
        for row in inp:
            k = row["id"]
            v = row["level"]
            if int(v) > 0:
                output[k] = int(v)
        return output

    def attack_report(self, report, report_id):
        """
        A report where we attacked a village
        """
        from_village = None
        from_player = None

        to_village = None
        to_player = None

        extra = {}

        losses = {}

        attacked = re.search(r'(\d{2}\.\d{2}\.\d{2} \d{2}:\d{2}:\d{2})<span class=\"small grey\">', report)
        if attacked:
            extra["when"] = int(datetime.strptime(attacked.group(1), "%d.%m.%y %H:%M:%S").timestamp())

        attacker = re.search(r'(?s)(<table id="attack_info_att".+?Agresor:.*?)<table id="attack_info_att_units"', report)
        if attacker:
            from_village_match = re.search(r'data-id="(\d+)"', attacker.group(1))
            if from_village_match:
                from_village = from_village_match.group(1)
                from_player_match = re.search(r'data-player="(\d+)"', attacker.group(1))
                from_player = from_player_match.group(1) if from_player_match else "0"
                
                # Fetch only the inner units table
                units = re.search(
                    r'(?s)<table id="attack_info_att_units"(.+?)</table>',
                    report,
                )
                if units:
                    sent_units = re.findall(r"(?s)<tr[^>]*>(.+?)</tr>", units.group(1))
                    if len(sent_units) >= 2:
                        extra["units_sent"] = self.re_unit(
                            Extractor.units_in_total(sent_units[1])
                        )
                    if len(sent_units) == 3:
                        extra["units_losses"] = self.re_unit(
                            Extractor.units_in_total(sent_units[2])
                        )
                        # Remove the from_player check or at least populate losses properly
                        if not self.game_state or str(from_player) == str(self.game_state.get("player", {}).get("id")) or "units_losses" in extra:
                            losses = extra["units_losses"]

        defender = re.search(r'(?s)(<table id="attack_info_def".+?Obro.*?)<table id="attack_info_def_units"', report)
        if defender:
            to_village_match = re.search(r'data-id="(\d+)"', defender.group(1))
            if to_village_match:
                to_village = to_village_match.group(1)
                to_player_match = re.search(r'data-player="(\d+)"', defender.group(1))
                to_player = to_player_match.group(1) if to_player_match else "0"
                
                # Fetch only the inner units table
                units = re.search(
                    r'(?s)<table id="attack_info_def_units"(.+?)</table>',
                    report,
                )
                if units:
                    def_units = re.findall(r"(?s)<tr[^>]*>(.+?)</tr>", units.group(1))
                    if len(def_units) >= 2:
                        extra["defence_units"] = self.re_unit(
                            Extractor.units_in_total(def_units[1])
                        )
                    if len(def_units) == 3:
                        extra["defence_losses"] = self.re_unit(
                            Extractor.units_in_total(def_units[2])
                        )
                        if self.game_state and "player" in self.game_state and str(to_player) == str(self.game_state["player"]["id"]):
                            losses = extra["defence_losses"]
        results = re.search(r'(?s)(<table id="attack_results".+?</table>)', report)
        report = report.replace('<span class="grey">.</span>', "")
        if results:
            loot = {}
            for loot_entry in re.findall(
                    r'<span class="icon header (wood|stone|iron)".+?</span>([\d\.,\s&nbsp;]+)', report
            ):
                amount = re.sub(r'[^\d]', '', loot_entry[1])
                loot[loot_entry[0]] = amount
            extra["loot"] = loot
            self.logger.info("attack report %s -> %s", from_village, to_village)

        scout_results = re.search(
            r'(?s)(<table id="attack_spy_resources".+?</table>)', report
        )
        if scout_results:
            self.logger.info("scout report %s -> %s", from_village, to_village)
            scout_buildings = re.search(
                r'(?s)<input id="attack_spy_building_data" type="hidden" value="(.+?)"',
                report,
            )
            if scout_buildings:
                raw = scout_buildings.group(1).replace("&quot;", '"')
                extra["buildings"] = self.re_building(json.loads(raw))
            found_res = {}
            for loot_entry in re.findall(
                    r'<span class="icon header (wood|stone|iron)".+?</span>([\d\.,\s&nbsp;]+)', scout_results.group(1)
            ):
                amount = re.sub(r'[^\d]', '', loot_entry[1])
                found_res[loot_entry[0]] = amount
            extra["resources"] = found_res
            units_away = re.search(
                r'(?s)(<table id="attack_spy_away".+?</table>)', report
            )
            if units_away:
                data_away = self.re_unit(Extractor.units_in_total(units_away.group(1)))
                extra["units_away"] = data_away

        attack_type = "scout" if scout_results and not results else "attack"

        # --- PERFORMANCE (POINT 3) ---
        # Update farm statistics immediately when processing the report
        player_id = self.game_state.get("player", {}).get("id") if self.game_state else None
        if attack_type == "attack" and to_village and (not player_id or str(from_player) == str(player_id)):
            try:
                self.update_farm_cache_stats(to_village, extra, losses)
            except Exception as e:
                self.logger.warning(f"Failed to update farm cache for {to_village}: {e}")
        # --- END PERFORMANCE ---

        # --- DB PERSISTENCE ---
        if _DB_AVAILABLE:
            try:
                loot_dict = extra.get("loot", {})
                scout_res = extra.get("resources", None)
                scout_bld = extra.get("buildings", None)
                # Check HTML indications of win/loss
                html_won_indicators = [
                    'image_attack_won', 'Pełna wygrana', 'wygrał', 'green.webp', 'yellow.webp',
                ]
                html_loss_indicators = [
                    'image_attack_lost', 'Porażka', 'red.webp',
                ]
                
                # Deduce win mathematically or via HTML
                won = (losses == {})
                if any(ind in report for ind in html_won_indicators):
                    won = True
                elif any(ind in report for ind in html_loss_indicators):
                    won = False
                elif losses and extra.get("units_sent"):
                    total_sent = sum(extra["units_sent"].values())
                    total_lost = sum(losses.values())
                    won = total_lost < total_sent

                attack_id = DatabaseManager.save_attack(
                    origin_id   = from_village,
                    target_id   = to_village,
                    troops_sent = extra.get("units_sent", {}),
                    loot        = {k: int(v) for k, v in loot_dict.items()},
                    won         = won,
                    scout_only  = (attack_type == "scout"),
                    arrived_at  = datetime.fromtimestamp(extra["when"]) if extra.get("when") else None,
                )
                if losses and attack_id:
                    DatabaseManager.save_units_lost(attack_id, {k: int(v) for k, v in losses.items()})
                if extra.get("defence_losses") and attack_id:
                    DatabaseManager.save_units_lost(
                        attack_id,
                        {k: int(v) for k, v in extra["defence_losses"].items()},
                        side="defender"
                    )
                DatabaseManager.save_report(
                    report_id   = report_id,
                    report_type = attack_type,
                    origin_id   = from_village,
                    dest_id     = to_village,
                    extra       = extra,
                    loot        = {k: int(v) for k, v in loot_dict.items()},
                    losses      = {k: int(v) for k, v in losses.items()} if losses else {},
                    scout_resources = {k: int(v) for k, v in scout_res.items()} if scout_res else None,
                    scout_buildings = scout_bld,
                )
                # Update production estimate from scout building data
                if scout_bld and to_village:
                    DatabaseManager.update_village_production(to_village, scout_bld)
            except Exception as _db_err:
                self.logger.debug("DB persistence error in attack_report: %s", _db_err)
        # --- END DB PERSISTENCE ---

        res = self.put(
            report_id, attack_type, from_village, to_village, data=extra, losses=losses
        )
        self.last_reports[report_id] = res
        return True

    # --- PERFORMANCE (POINT 3) ---
    def update_farm_cache_stats(self, village_id, extra_data, losses):
        """
        Updates the AttackCache with loot and loss statistics
        This logic is moved from manager.py to run on report processing
        """
        if not village_id:
            return

        cache_entry = AttackCache.get_cache(village_id)
        if cache_entry is None:
            self.logger.debug(f"No attack cache found for {village_id}, creating new entry from report.")
            cache_entry = {
                "scout": False,
                "safe": True,
                "high_profile": False,
                "low_profile": False,
                "last_attack": 0,
            }

        # Initialize stats if not present
        cache_entry.setdefault("attack_count", 0)
        cache_entry.setdefault("total_loot", {"wood": 0, "stone": 0, "iron": 0})
        cache_entry.setdefault("total_losses", 0)
        cache_entry.setdefault("total_sent", 0)

        # Update stats
        cache_entry["attack_count"] += 1

        if extra_data.get("loot"):
            loot = extra_data["loot"]
            for res, amount in loot.items():
                cache_entry["total_loot"][res] = cache_entry["total_loot"].get(res, 0) + int(amount)

        if extra_data.get("units_sent"):
            cache_entry["total_sent"] += sum(int(v) for v in extra_data["units_sent"].values())
            cache_entry["last_sent"] = extra_data["units_sent"]

        if losses:
            cache_entry["total_losses"] += sum(int(v) for v in losses.values())
        
        # Save was_lost flag based on if there were any losses this run
        cache_entry["was_lost"] = len(losses) > 0 if losses else False
        cache_entry["last_losses"] = losses if losses else {}

        # Apply farm profile logic
        percentage_lost = (cache_entry["total_losses"] / cache_entry["total_sent"] * 100) if cache_entry["total_sent"] > 0 else 0
        total_loot_sum = sum(cache_entry["total_loot"].values())
        avg_loot = total_loot_sum / cache_entry["attack_count"] if cache_entry["attack_count"] > 0 else 0

        if cache_entry["attack_count"] > 3:
            if avg_loot < 100:
                if not cache_entry.get("low_profile"):
                    self.logger.info(f"Farm {village_id} has low resources ({avg_loot:.0f} avg), setting low_profile.")
                    cache_entry["low_profile"] = True
            elif avg_loot > 500:
                if not cache_entry.get("high_profile"):
                    self.logger.info(f"Farm {village_id} has high resources ({avg_loot:.0f} avg), setting high_profile.")
                    cache_entry["high_profile"] = True
                    cache_entry["low_profile"] = False

        if percentage_lost > 20:
            if not cache_entry.get("low_profile"):
                self.logger.warning(f"Farm {village_id} has high losses ({percentage_lost:.0f}%), setting low_profile.")
                cache_entry["low_profile"] = True
                cache_entry["high_profile"] = False

        if percentage_lost > 50 and cache_entry["attack_count"] > 10:
            if cache_entry.get("safe", True):
                self.logger.critical(f"Farm {village_id} is unsafe ({percentage_lost:.0f}% loss), disabling farm.")
                cache_entry["safe"] = False

        AttackCache.set_cache(village_id, cache_entry)
    # --- END PERFORMANCE ---

    def put(
            self,
            report_id,
            report_type,
            origin_village=None,
            dest_village=None,
            losses=None,
            data=None,
    ):
        """
        Creates a report file
        """
        if losses is None:
            losses = {}
        if data is None:
            data = {}
        output = {
            "type": report_type,
            "origin": origin_village,
            "dest": dest_village,
            "losses": losses,
            "extra": data,
        }
        ReportCache.set_cache(report_id, output)
        self.logger.info(
            "Processed %s report with id %s", report_type, str(report_id)
        )
        return output


class ReportCache:
    """
    File cache for local reports
    """
    @staticmethod
    def get_cache(report_id):
        """
        Reads a report entry
        """
        return FileManager.load_json_file(f"cache/reports/{report_id}.json")

    @staticmethod
    def set_cache(report_id, entry):
        """
        Creates a report entry
        """
        FileManager.save_json_file(entry, f"cache/reports/{report_id}.json")

    @staticmethod
    def cache_grab():
        """
        Reads all locally stored reports
        """
        output = {}

        for existing in FileManager.list_directory("cache/reports", ends_with=".json"):
            output[existing.replace(".json", "")] = FileManager.load_json_file(f"cache/reports/{existing}")
        return output
