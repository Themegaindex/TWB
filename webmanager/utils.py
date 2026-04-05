import collections
import json
import os
import signal
import subprocess

import psutil


class DataReader:
    @staticmethod
    def cache_grab(cache_location):
        output = {}
        if cache_location == "managed":
            try:
                import sys
                sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
                from core.database import DatabaseManager, DBVillageSettings
                db_s = DatabaseManager._session()
                if db_s:
                    for row in db_s.query(DBVillageSettings).all():
                        if row.settings:
                            output[row.village_id] = row.settings
                    db_s.close()
            except Exception as e:
                print(f"Error reading managed setting from DB: {e}")
            return output

        if cache_location == "villages":
            # Return full world villages from DB
            try:
                import sys
                sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
                from core.database import DatabaseManager
                # get_all_villages now returns a Dict[str, Dict] join-populated
                return DatabaseManager.get_all_villages(limit=25000)
            except Exception as e:
                print(f"Error reading villages from DB: {e}")
                return output

        c_path = os.path.join(
            os.path.dirname(__file__),
            "..",
            "cache",
            cache_location
        )
        if not os.path.exists(c_path):
            return output
            
        for existing in os.listdir(c_path):
            existing = str(existing)
            if not existing.endswith(".json"):
                continue
            t_path = os.path.join(os.path.dirname(__file__), "..", "cache", cache_location, existing)
            with open(t_path, 'r') as f:
                try:
                    output[existing.replace('.json', '')] = json.load(f)
                except Exception as e:
                    print("Cache read error for %s: %s. Removing broken entry" % (t_path, str(e)))
                    f.close()
                    os.remove(t_path)

        return output

    @staticmethod
    def template_grab(template_location):
        output = []
        template_location = template_location.replace('.', '/')
        c_path = os.path.join(os.path.dirname(__file__), "..", template_location)
        for existing in os.listdir(c_path):
            existing = str(existing)
            if not existing.endswith(".txt"):
                continue
            output.append(existing.split('.')[0])
        return output

    @staticmethod
    def config_grab():
        with open(os.path.join(os.path.dirname(__file__), "..", "config.json"), 'r') as f:
            return json.load(f)

    @staticmethod
    def config_set(parameter, value):
        try:
            value = json.loads(value)
        except:
            pass
        config_file_path = os.path.join(os.path.dirname(__file__), "..", "config.json")
        with open(config_file_path, 'r') as config_file:
            template = json.load(config_file, object_pairs_hook=collections.OrderedDict)
            if "." in parameter:
                section, param = parameter.split('.')
                template[section][param] = value
            else:
                template[parameter] = value
            with open(config_file_path, 'w') as newcf:
                json.dump(template, newcf, indent=2, sort_keys=False)
                print("Deployed new configuration file")
                return True

    @staticmethod
    def village_config_set(village_id, parameter, value):
        config_file_path = os.path.join(os.path.dirname(__file__), "..", "config.json")
        with open(config_file_path, 'r') as config_file:
            template = json.load(config_file, object_pairs_hook=collections.OrderedDict)
            if village_id not in template['villages']:
                return False
            try:
                template['villages'][str(village_id)][parameter] = json.loads(value)
            except json.decoder.JSONDecodeError:
                template['villages'][str(village_id)][parameter] = value
            with open(config_file_path, 'w') as newcf:
                json.dump(template, newcf, indent=2, sort_keys=False)
                print("Deployed new configuration file")
                return True

    @staticmethod
    def get_session():
        session_data = {"raw": "", "endpoint": "", "server": "", "world": "", "cookies": {}}
        c_path = os.path.join(os.path.dirname(__file__), "..", "cache", "session.json")
        
        if os.path.exists(c_path):
            try:
                with open(c_path, 'r') as session_file:
                    session_data = json.load(session_file)
            except Exception as e:
                print(f"Error reading session.json: {e}")

        # Fallback to DB if world is still missing
        if not session_data.get('server') or not session_data.get('world'):
            try:
                import sys
                sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
                from core.database import DatabaseManager, DBSession
                db_s = DatabaseManager._session()
                if db_s:
                    row = db_s.query(DBSession).order_by(DBSession.updated_at.desc()).first()
                    if row:
                        session_data['endpoint'] = row.endpoint
                        session_data['server'] = row.server
                        session_data['world'] = row.server
                        session_data['cookies'] = row.cookies
                    db_s.close()
            except Exception as e:
                print(f"Error reading session from DB: {e}")

        # Ensure world is set if server is set
        if session_data.get('server'):
            session_data['world'] = session_data['server']
        
        # Hard fallback to a default if still empty (optional, but prevents none.plemiona.pl)
        if not session_data.get('world'):
             session_data['world'] = 'pl227' # A sensible default for Polish users

        # Construct raw cookie string
        if 'cookies' in session_data and isinstance(session_data['cookies'], dict):
            cookies = []
            for c, v in session_data['cookies'].items():
                cookies.append("%s=%s" % (c, v))
            session_data['raw'] = ';'.join(cookies)
        
        return session_data


class TemplateManager:
    @staticmethod
    def get_all_templates():
        """Returns all templates categorized by type."""
        base_path = os.path.join(os.path.dirname(__file__), "..", "templates")
        categories = ["builder", "troops", "offensive"]
        output = {cat: [] for cat in categories}

        for cat in categories:
            cat_path = os.path.join(base_path, cat)
            if not os.path.exists(cat_path):
                continue
            for existing in os.listdir(cat_path):
                if existing.endswith(".txt"):
                    output[cat].append(existing)
        return output

    @staticmethod
    def get_template_content(category, name):
        """Returns the content and parsed structure of a template."""
        t_path = os.path.join(os.path.dirname(__file__), "..", "templates", category, name)
        if not os.path.exists(t_path):
            return None

        with open(t_path, "r") as f:
            raw = f.read()

        parsed = None
        if category == "builder":
            parsed = TemplateManager.parse_builder(raw.splitlines())
        else:
            try:
                parsed = json.loads(raw)
            except (json.JSONDecodeError, TypeError):
                parsed = raw

        return {"raw": raw, "parsed": parsed}

    @staticmethod
    def parse_builder(t_list):
        out_data = {}
        rows = []
        for entry in t_list:
            entry = entry.strip()
            if not entry or entry.startswith("#") or ":" not in entry:
                continue
            try:
                building, next_level = entry.split(":")
                next_level = int(next_level)
                old = out_data.get(building, 0)
                rows.append({"building": building, "from": old, "to": next_level})
                out_data[building] = next_level
            except:
                continue
        return rows

    @staticmethod
    def save_template(category, name, content):
        """Saves a template to disk."""
        if not name.endswith(".txt"):
            name += ".txt"
        
        # Security check: prevent directory traversal
        name = os.path.basename(name)
        
        t_path = os.path.join(os.path.dirname(__file__), "..", "templates", category, name)
        
        # Ensure directory exists
        os.makedirs(os.path.dirname(t_path), exist_ok=True)
        
        with open(t_path, "w") as f:
            f.write(content)
        return True

    @staticmethod
    def delete_template(category, name):
        """Deletes a template from disk."""
        t_path = os.path.join(os.path.dirname(__file__), "..", "templates", category, name)
        if os.path.exists(t_path):
            os.remove(t_path)
            return True
        return False


class MapBuilder:

    @staticmethod
    def build(villages, current_village=None, size=15, attacks=None):
        out_map = {}
        cx, cy = 500, 500
        
        # 1. Determine center coordinates
        if current_village and str(current_village) in villages:
            v_center = villages[str(current_village)]
            cx, cy = int(v_center.get('x', 500)), int(v_center.get('y', 500))
        
        # 2. Determine bounds
        min_x = cx - size
        max_x = cx + size
        min_y = cy - size
        max_y = cy + size

        # 3. Create a coordinate-based lookup for the grid
        grid_lookup = {}
        for vid, vdata in villages.items():
            vx, vy = int(vdata.get('x', -1)), int(vdata.get('y', -1))
            if min_x <= vx <= max_x and min_y <= vy <= max_y:
                grid_lookup[f"{vx}:{vy}"] = vdata

        # 4. Build the actual grid for the template
        for x in range(min_x, max_x + 1):
            x_rel = x - min_x
            out_map[x_rel] = {}
            for y in range(min_y, max_y + 1):
                y_rel = y - min_y
                coord_key = f"{x}:{y}"
                
                v_entry = grid_lookup.get(coord_key)
                if v_entry and attacks and v_entry['id'] in attacks:
                    v_entry['recent_attack'] = attacks[v_entry['id']]
                
                out_map[x_rel][y_rel] = v_entry

        return {
            "grid": out_map, 
            "bounds": {"min_x": min_x, "min_y": min_y, "max_x": max_x, "max_y": max_y},
            "center": [cx, cy]
        }


class BotManager:
    pid = None

    def is_running(self):
        if not self.pid:
            return False
        if psutil.pid_exists(self.pid):
            return True
        self.pid = False
        return False

    def start(self):
        wd = os.path.join(os.path.dirname(__file__), "..")
        proc = subprocess.Popen("python twb.py", cwd=wd, shell=True)
        self.pid = proc.pid
        print("Bot started successfully")

    def stop(self):
        if self.is_running():
            os.kill(self.pid, signal.SIGTERM)
            print("Bot stopped successfully")
