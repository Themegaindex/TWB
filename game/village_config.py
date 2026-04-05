import logging
from core.extractors import Extractor

class VillageConfigMixin:
    def get_config(self, section, parameter, default=None):
        if section not in self.config: return default
        if parameter not in self.config[section]: return default
        return self.config[section][parameter]

    def get_village_config(self, village_id, parameter, default=None):
        if village_id in self.config["villages"]:
            vdata = self.config["villages"][village_id]
            if parameter in vdata:
                return vdata[parameter]
        
        # Fallback to village_template if present in config
        if "village_template" in self.config:
            if parameter in self.config["village_template"]:
                return self.config["village_template"][parameter]
                
        return default

    def village_init(self):
        url = "game.php?screen=overview&intro"
        if self.village_id: url = f"game.php?village={self.village_id}&screen=overview"
        data = self.wrapper.get_url(url)
        if data:
            self.game_data = Extractor.game_state(data)
            self.overview_html = data.text
        
        if self.game_data:
            if not self.village_id: self.village_id = str(self.game_data.get("village", {}).get("id", "0"))
            vname = self.game_data.get("village", {}).get("name", self.village_id)
            self.logger = logging.getLogger("Village %s" % vname)
            self.wrapper.reporter.report(self.village_id, "TWB_START", "Starting run for village: %s" % vname)
            return data
        else:
            self.logger = logging.getLogger(f"Village {self.village_id if self.village_id else 'Init'}")
            
            # Check for bot protection in the response text if available
            error_reason = "Unknown"
            if data:
                if "bot_protect" in data.text or "captcha" in data.text:
                    error_reason = "Bot protection (captcha) detected"
                elif "login_form" in data.text:
                    error_reason = "Session expired / Logged out"
            
            self.logger.error(f"Could not read game state for village {self.village_id if self.village_id else ''}. Reason: {error_reason}")
            from core.exceptions import VillageInitException
            raise VillageInitException(f"Error reading game data for village {self.village_id}: {error_reason}")

    def set_world_config(self):
        self.disabled_units = []
        if not self.get_config(section="world", parameter="archers_enabled", default=True):
            self.disabled_units.extend(["archer", "marcher"])
        if not self.get_config(section="world", parameter="building_destruction_enabled", default=True):
            self.disabled_units.extend(["ram", "catapult"])
        if not self.get_config(section="world", parameter="scouts_enabled", default=True):
            self.disabled_units.append("spy")
        if not self.get_config(section="world", parameter="knights_enabled", default=True):
            self.disabled_units.append("knight")
        if self.get_config(section="server", parameter="server_on_twstats", default=False):
            self.twp.run(world=self.get_config(section="server", parameter="server"))
