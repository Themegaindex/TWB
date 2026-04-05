"""
Map management, pls don't read this code.
"""
import logging
import math
import time

from core.extractors import Extractor
from core.filemanager import FileManager


class Map:
    """
    Class to manage the world around you
    """
    wrapper = None
    village_id = None
    map_data = []
    villages = {}
    my_location = None
    map_pos = {}
    last_fetch = 0
    fetch_delay = 8

    def __init__(self, wrapper=None, village_id=None):
        """
        Creates the map files
        """
        self.wrapper = wrapper
        self.village_id = village_id

    def get_map(self, radius=0, fetch_delay=8, search_radius=None):
        """
        Fetch the map every 24ish hours and update the cache entries
        """
        if self.last_fetch + (fetch_delay * 3600) > time.time():
            return
        self.last_fetch = time.time()
        res = self.wrapper.get_action(village_id=self.village_id, action="map")
        game_state = Extractor.game_state(res)
        self.map_data = Extractor.map_data(res)
        self.parse_map_tiles(self.map_data, game_state)

        # Active Map Scanning logic
        if radius > 0 and self.my_location:
            # We want to scan `radius` number of 20x20 sectors in each direction
            # For each expanded block, we make an ajax request
            for dx in range(-radius, radius + 1):
                for dy in range(-radius, radius + 1):
                    if dx == 0 and dy == 0:
                        continue # Already loaded from initial map page
                    
                    req_x = int(self.my_location[0]) + dx * 20
                    req_y = int(self.my_location[1]) + dy * 20
                    
                    if req_x < 0 or req_x > 1000 or req_y < 0 or req_y > 1000:
                        continue

                    # If search_radius is provided, skip sectors that are entirely outside of it
                    if search_radius:
                        # Find closest point in sector (req_x, req_y) to (req_x+19, req_y+19)
                        # to our current location
                        closest_x = max(req_x, min(int(self.my_location[0]), req_x + 19))
                        closest_y = max(req_y, min(int(self.my_location[1]), req_y + 19))
                        
                        dist_to_sector = math.sqrt(
                            (closest_x - self.my_location[0]) ** 2
                            + (closest_y - self.my_location[1]) ** 2
                        )
                        if dist_to_sector > search_radius:
                            continue

                    # Load exact coordinate map API
                    action_url = f"map&x={req_x}&y={req_y}"
                    res_scan = self.wrapper.get_action(village_id=self.village_id, action=action_url)
                    
                    # Random delay between sector requests to avoid bot detection
                    import random
                    time.sleep(random.uniform(1.2, 3.5))

                    scan_data = Extractor.map_data(res_scan)
                    if scan_data:
                        self.parse_map_tiles(scan_data, game_state)

        if not self.map_data or not self.villages:
            return self.get_map_old(game_state=game_state)
        return True

    def parse_map_tiles(self, map_data, game_state):
        if map_data:
            for tile in map_data:
                data = tile["data"]
                x = int(data["x"])
                y = int(data["y"])
                vdata = data["villages"]
                # Fix broken parsing                 
                if type(vdata) is dict:
                    cdata = [{}] * 20
                    for k, v in vdata.items():
                        if type(v) is not dict:
                            cdata[int(k)] = {0: item[0:] for item in v}
                        else:
                            cdata[int(k)] = v
                    vdata = cdata
                for lon, val in enumerate(vdata):
                    if not val:
                        continue
                    # Force dict type to iterate properly
                    if type(val) != dict:
                        val = {i: val[i] for i in range(0, len(val))}
                    for lat, entry in val.items():
                        if not lat:
                            continue
                        coords = [x + int(lon), y + int(lat)]
                        if entry[0] == str(self.village_id):
                            self.my_location = coords

                        self.build_cache_entry(location=coords, entry=entry)
                if not self.my_location:
                    self.my_location = [
                        game_state["village"]["x"],
                        game_state["village"]["y"],
                    ]

    def get_map_old(self, game_state):
        """
        Old method of parsing the map, might work, might not, who knows
        """
        if self.map_data:
            for tile in self.map_data:
                data = tile["data"]
                x = int(data["x"])
                y = int(data["y"])
                vdata = data["villages"]
                for lon, lon_val in enumerate(vdata):
                    try:
                        for lat in vdata[lon]:
                            coords = [x + int(lon), y + int(lat)]
                            entry = vdata[lon][lat]
                            if entry[0] == str(self.village_id):
                                self.my_location = coords

                            self.build_cache_entry(location=coords, entry=entry)
                    except:
                        raise
            if not self.my_location:
                self.my_location = [
                    game_state["village"]["x"],
                    game_state["village"]["y"],
                ]
        if not self.map_data or not self.villages:
            logging.warning(
                "Error reading map state for village %s, farming might not work properly",
                self.village_id
            )
            return False
        return True

    def build_cache_entry(self, location, entry):
        """
        Builds a cache entry based on their weird data structure
        """
        vid = entry[0]
        name = entry[2]
        try:
            points = int(entry[3].replace(".", ""))
        except ValueError:
            # Breaks farming logic on event villages
            return
        player = entry[4]
        bonus = entry[6]
        clan = entry[11]
        structure = {
            "id": vid,
            "name": name,
            "location": location,
            "bonus": bonus,
            "points": points,
            "safe": False,
            "scout": False,
            "tribe": clan,
            "owner": player,
            "buildings": {},
            "resources": {},
        }
        self.map_pos[vid] = location
        try:
            from core.database import DatabaseManager
            DatabaseManager.upsert_village(
                vid=vid,
                name=name,
                x=location[0],
                y=location[1],
                points=points,
                owner_id=player
            )
        except Exception as e:
            logging.error(f"Failed to upsert village {vid} to DB: {e}")
        self.villages[vid] = structure

    def in_cache(self, vid):
        """
        Checks if a village is already in the database
        """
        try:
            from core.database import DatabaseManager
            return DatabaseManager.get_village(vid)
        except Exception:
            return None

    def get_dist(self, ext_loc):
        """
        Calculates distance from current village to coords
        """
        distance = math.sqrt(
            ((self.my_location[0] - ext_loc[0]) ** 2)
            + ((self.my_location[1] - ext_loc[1]) ** 2)
        )
        return distance


class MapCache:
    """
    Holds a cache of all found villages within a certain distance
    """
    @staticmethod
    def get_cache(village_id):
        """
        Get data from the database
        """
        try:
            from core.database import DatabaseManager
            res = DatabaseManager.get_village(village_id)
            if res:
                # Convert DB format back to map structure format if needed
                return {
                    "id": res["id"],
                    "name": res["name"],
                    "location": [res["x"], res["y"]],
                    "points": res["points"],
                    "owner": res["owner_id"]
                }
            return None
        except Exception:
            return None

    @staticmethod
    def set_cache(village_id, entry):
        """
        Creates or updates a database entry
        """
        try:
            from core.database import DatabaseManager
            DatabaseManager.upsert_village(
                vid=village_id,
                name=entry["name"],
                x=entry["location"][0],
                y=entry["location"][1],
                points=entry["points"],
                owner_id=entry["owner"]
            )
        except Exception as e:
            logging.error(f"Failed to set map cache for {village_id}: {e}")
