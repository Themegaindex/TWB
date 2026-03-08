import json
import os
import sys
sys.path.insert(0, "../")

from flask import Flask, jsonify, send_from_directory, request, render_template
from flask_cors import CORS

try:
    from webmanager.helpfile import help_file, buildings
    from webmanager.utils import DataReader, BotManager, MapBuilder, BuildingTemplateManager
except ImportError:
    from helpfile import help_file, buildings
    from utils import DataReader, BotManager, MapBuilder, BuildingTemplateManager

try:
    sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
    from core.database import DatabaseManager
    _DB_OK = True
except Exception:
    _DB_OK = False

bm = BotManager()

app = Flask(__name__)
CORS(app, resources={r"/*": {"origins": "*"}})
app.config["DEBUG"] = True

@app.after_request
def add_pna_headers(response):
    """ Allow Chrome Private Network Access (PNA) preflights and CORS """
    response.headers["Access-Control-Allow-Origin"] = "*"
    response.headers["Access-Control-Allow-Methods"] = "GET, POST, OPTIONS, PUT, DELETE"
    response.headers["Access-Control-Allow-Headers"] = "Content-Type, Authorization, X-Requested-With"
    response.headers["Access-Control-Allow-Private-Network"] = "true"
    # Ensure preflight (OPTIONS) returns 200 for PNA
    if request.method == 'OPTIONS':
        response.status_code = 200
    return response


def pre_process_bool(key, value, village_id=None):
    if village_id:
        if value:
            return '<button class="btn btn-sm btn-block btn-success" data-village-id="%s" data-type-option="%s" data-type="toggle">Enabled</button>' % (
            village_id, key)
        else:
            return '<button class="btn btn-sm btn-block btn-danger" data-village-id="%s" data-type-option="%s" data-type="toggle">Disabled</button>' % (
            village_id, key)
    if value:
        return '<button class="btn btn-sm btn-block btn-success" data-type-option="%s" data-type="toggle">Enabled</button>' % key
    else:
        return '<button class="btn btn-sm btn-block btn-danger" data-type-option="%s" data-type="toggle">Disabled</button>' % key


def preprocess_select(key, value, templates, village_id=None):
    output = '<select data-type-option="%s" data-type="select" class="form-control">' % key
    if village_id:
        output = '<select data-type-option="%s" data-village-id="%s" data-type="select" class="form-control">' % (
        key, village_id)

    for template in DataReader.template_grab(templates):
        output += '<option value="%s" %s>%s</option>' % (template, 'selected' if template == value else '', template)
    output += '</select>'
    return output


def pre_process_string(key, value, village_id=None):
    templates = {
        'units.default': 'templates.troops',
        'village.units': 'templates.troops',
        'building.default': 'templates.builder',
        'village_template.units': 'templates.troops',
        'village.building': 'templates.builder',
        'village_template.building': 'templates.builder'
    }
    if key in templates:
        return preprocess_select(key, value, templates[key], village_id)
    if village_id:
        return '<input type="text" class="form-control" data-village-id="%s" data-type="text" value="%s" data-type-option="%s" />' % (
        village_id, value, key)
    else:
        return '<input type="text" class="form-control" data-type="text" value="%s" data-type-option="%s" />' % (
            value, key)


def pre_process_number(key, value, village_id=None):
    if village_id:
        return '<input type="number" data-type="number" class="form-control" data-village-id="%s" value="%s" data-type-option="%s" />' % (
        village_id, value, key)
    return '<input type="number" data-type="number" class="form-control" value="%s" data-type-option="%s" />' % (
    value, key)


def pre_process_list(key, value, village_id=None):
    if village_id:
        return '<input type="text" data-type="list" class="form-control" data-village-id="%s" value="%s" data-type-option="%s" />' % (
        village_id, ', '.join(value), key)
    return '<input type="number" data-type="list" class="form-control" value="%s" data-type-option="%s" />' % (
    ', '.join(value), key)


def fancy(key):
    name = key
    if '.' in name:
        name = name.split('.')[1]
    name = name[0].upper() + name[1:]
    out = '<hr /><strong>%s</strong>' % name
    help_txt = None
    help_key = key
    help_key = help_key.replace('village_template', 'village')
    if help_key in help_file:
        help_txt = help_file[help_key]
    if help_txt:
        out += '<br /><i>%s</i>' % help_txt
    return out


def pre_process_config():
    # TODO get generic config
    config = sync()['config']
    to_hide = ["build", "villages"]
    sections = {}
    for section in config:
        if section in to_hide:
            continue
        config_data = ""
        for parameter in config[section]:
            value = config[section][parameter]
            kvp = "%s.%s" % (section, parameter)
            if type(value) == bool:
                config_data += '%s %s' % (fancy(kvp), pre_process_bool(kvp, value))
            if type(value) == str:
                config_data += '%s %s' % (fancy(kvp), pre_process_string(kvp, value))
            if type(value) == list:
                config_data += '%s %s' % (fancy(kvp), pre_process_list(kvp, value))
            if type(value) == int or type(value) == float:
                config_data += '%s %s' % (fancy(kvp), pre_process_number(kvp, value))
        sections[section] = config_data
    return sections


def pre_process_village_config(village_id):
    config = sync()['config']['villages']
    if village_id in config:
        config = config[village_id]
    else:
        config = config[config.keys()[0]]
    config_data = ""
    for parameter in config:
        value = config[parameter]
        kvp = "village.%s" % parameter
        if type(value) == bool:
            config_data += '%s %s' % (fancy(kvp), pre_process_bool(kvp, value, village_id))
        if type(value) == str:
            config_data += '%s %s' % (fancy(kvp), pre_process_string(kvp, value, village_id))
        if type(value) == list:
            config_data += '%s %s' % (fancy(kvp), pre_process_list(kvp, value, village_id))
        if type(value) == int or type(value) == float:
            config_data += '%s %s' % (fancy(kvp), pre_process_number(kvp, value, village_id))
    return config_data


def sync():
    reports = DataReader.cache_grab("reports")
    villages = DataReader.cache_grab("villages")
    attacks = DataReader.cache_grab("attacks")
    config = DataReader.config_grab()
    managed = DataReader.cache_grab("managed")
    bot_status = bm.is_running()

    def parse_report_id(r_id):
        try:
            return int(r_id)
        except ValueError:
            nums = ''.join(filter(str.isdigit, str(r_id)))
            return int(nums) if nums else 0

    sort_reports = {key: value for key, value in sorted(reports.items(), key=lambda item: parse_report_id(item[0]))}
    n_items = {k: sort_reports[k] for k in list(sort_reports)[:100]}

    report_counts = {}
    for r_id, r_data in reports.items():
        dest = r_data.get('dest')
        if dest:
            report_counts[dest] = report_counts.get(dest, 0) + 1

    for v_id, v_data in villages.items():
        v_data['report_count'] = report_counts.get(v_id, 0)

    out_struct = {
        "attacks": attacks,
        "villages": villages,
        "config": config,
        "reports": n_items,
        "bot": managed,
        "status": bot_status
    }
    return out_struct


@app.route('/api/get', methods=['GET'])
def get_vars():
    return jsonify(sync())


@app.route('/api/village_attacks', methods=['GET'])
def api_village_attacks():
    """
    Returns full attack history + production estimate for a given village.
    Frontend map uses this for the detail panel.
    """
    vid = request.args.get('vid', None)
    if not vid:
        return jsonify({'error': 'vid required'}), 400
    if not _DB_OK:
        return jsonify({'error': 'database not available'}), 503

    attacks  = DatabaseManager.get_attack_history(vid, limit=50)
    village  = DatabaseManager.get_village(vid)
    prod     = None
    if village:
        prod = {
            'wood':  village.get('wood_prod', 0),
            'stone': village.get('stone_prod', 0),
            'iron':  village.get('iron_prod', 0),
        }

    # Collect all losses across these attacks
    losses = []
    for a in attacks:
        for l in a.get('losses', []):
            losses.append(l)

    return jsonify({'attacks': attacks, 'production': prod, 'losses': losses})


@app.route('/api/cookie_webhook', methods=['POST'])
def cookie_webhook():
    """
    Webhook endpoint called by the browser extension.
    Receives a JSON body: { "cookies": "sid=xxx; pl_auth=yyy; ...", "endpoint": "https://pl227.plemiona.pl/game.php" }
    Updates the local session cache so the bot uses the fresh cookie without restart.
    """
    data = request.get_json(force=True, silent=True)
    if not data or 'cookies' not in data:
        return jsonify({'ok': False, 'error': 'missing cookies field'}), 400

    raw_cookie  = data['cookies'].strip()
    endpoint    = data.get('endpoint', '')

    # Parse cookies string into dict for logging/fallback
    cookies = {}
    for part in raw_cookie.split(';'):
        part = part.strip()
        if '=' in part:
            k, _, v = part.partition('=')
            cookies[k.strip()] = v.strip()

    try:
        from core.database import DatabaseManager, DBSession
        db_s = DatabaseManager._session()
        if db_s:
            # Clear old and write new
            db_s.query(DBSession).delete()
            
            user_agent_str = data.get('userAgent', '')
            
            new_sess = DBSession(
                endpoint=endpoint,
                server=endpoint.split("//")[1].split(".")[0] if "//" in endpoint else "",
                cookies=cookies,
                user_agent=user_agent_str
            )
            db_s.add(new_sess)
            db_s.commit()
            db_s.close()
        
        return jsonify({'ok': True, 'message': 'Session updated in DB', 'cookies_count': len(cookies)})
    except Exception as e:
        return jsonify({'ok': False, 'error': str(e)}), 500


@app.route('/api/plugin_report', methods=['POST'])
def api_plugin_report():
    """
    Receives raw report HTML directly from the browser plugin.
    Verifies if report exists, if not, parses it using ReportManager.
    """
    data = request.get_json(force=True, silent=True)
    if not data or 'html' not in data or 'report_id' not in data:
        return jsonify({'ok': False, 'message': 'Brak HTML lub ID raportu'}), 400
        
    report_id = str(data['report_id'])
    html = data['html']
    
    import logging
    log = logging.getLogger("PluginReport")
    
    from core.database import DatabaseManager
    # Check if report already exists in DB
    if hasattr(DatabaseManager, "get_report") and DatabaseManager.get_report(report_id):
        log.info(f"Raport {report_id} otrzymał ping z wtyczki, ale już był w bazie.")
        return jsonify({'ok': True, 'message': 'Raport już jest (Pominięto).'})
        
    try:
        from game.reports import ReportManager
        import re
        rm = ReportManager(wrapper=None, village_id="0")
        rm.logger = log
        
        get_type = re.search(r'class="report_(\w+)', html)
        if not get_type:
            log.warning(f"Nie udało się wczytać raportu {report_id}: zły / nie znana struktura html")
            return jsonify({'ok': False, 'message': 'Nie znana struktura html'}), 400
            
        report_type = get_type.group(1)
        if report_type == "ReportAttack":
            # The attack_report function internally inserts to DB if successful
            rm.attack_report(html, report_id)
            log.info(f"Raport {report_id} został POMYŚLNIE zaczytany i zaktualizowany!")
            return jsonify({'ok': True, 'message': 'Raport zaczytany (Atak).'})
        else:
            log.info(f"Odebrano z wtyczki strukturę raportu ignorowanego typu: {report_type}")
            return jsonify({'ok': True, 'message': f'Zignorowano typ: {report_type}'})
            
    except Exception as e:
        log.error(f"Nie udało się wczytać raportu {report_id} poprzez parsowanie struktury: złe komponenty? Błąd: {e}")
        return jsonify({'ok': False, 'message': f'Błąd wczytywania: {str(e)}'}), 500

@app.route('/api/plugin/map', methods=['POST'])
def api_plugin_map():
    """
    Receives raw map data chunks directly from the browser plugin.
    Mass UPSERTS villages into PostgreSQL to keep the bot's map cache live without extra traffic.
    """
    data = request.get_json(force=True, silent=True)
    if not data or 'villages' not in data:
        return jsonify({'ok': False, 'message': 'Brak danych mapy'}), 400
        
    try:
        from core.database import DatabaseManager, DBVillage
        from sqlalchemy.dialects.postgresql import insert
        from datetime import datetime
        
        db_s = DatabaseManager._session()
        if not db_s:
            return jsonify({'ok': False, 'message': 'DB Error'}), 500
            
        updated = 0
        for v in data['villages']:
            # Upsert logic
            stmt = insert(DBVillage).values(
                id=str(v.get('id')),
                name=v.get('name', ''),
                x=int(v.get('x', 0)),
                y=int(v.get('y', 0)),
                points=int(v.get('points', 0)),
                owner_id=str(v.get('owner', '0')),
                last_seen=datetime.utcnow()
            )
            stmt = stmt.on_conflict_do_update(
                index_elements=['id'],
                set_={
                    'name': stmt.excluded.name,
                    'points': stmt.excluded.points,
                    'owner_id': stmt.excluded.owner_id,
                    'last_seen': stmt.excluded.last_seen
                }
            )
            db_s.execute(stmt)
            updated += 1
            
        db_s.commit()
        db_s.close()
        
        import logging
        log = logging.getLogger("PluginMap")
        log.info(f"Odebrano z wtyczki i zaktualizowano {updated} wiosek na naszej lokalnej mapie!")
        
        return jsonify({'ok': True, 'message': f'Zaktualizowano {updated} wiosek z mapy'})
    except Exception as e:
        import traceback
        traceback.print_exc()
        return jsonify({'ok': False, 'error': str(e)}), 500

@app.route('/api/force_reports', methods=['POST'])
def api_force_reports():
    """
    Trigger reading backwards historical reports for statistics.
    """
    try:
        data = request.get_json(silent=True) or {}
        pages = str(data.get('pages', 5))
        import subprocess
        script_path = os.path.join(os.path.dirname(__file__), '..', 'force_read_reports.py')
        if not os.path.exists(script_path):
            return jsonify({'ok': False, 'message': 'Skrypt force_read_reports.py nie istnieje.'}), 404
            
        subprocess.Popen([sys.executable, script_path, pages], cwd=os.path.join(os.path.dirname(__file__), '..'))
        return jsonify({'ok': True, 'message': f'Pobieranie {pages} stron historycznych raportów rozpoczęte w tle. Zobacz logi w konsoli.'})
    except Exception as e:
        return jsonify({'ok': False, 'message': str(e)}), 500


@app.route('/api/logs', methods=['GET'])
def get_logs():
    """ Returns last 100 lines of the bot.log file """
    log_path = os.path.join(os.path.dirname(__file__), '..', 'cache', 'bot.log')
    if not os.path.exists(log_path):
        return jsonify({'logs': 'Brak logów.'})
    try:
        with open(log_path, 'r', encoding='utf-8') as f:
            lines = f.readlines()
            return jsonify({'logs': ''.join(lines[-200:])})
    except Exception as e:
        return jsonify({'logs': f'Error reading log: {str(e)}'})

@app.route('/api/logs/download', methods=['GET'])
def download_logs():
    """ Downloads the entire bot.log file """
    cache_dir = os.path.join(os.path.dirname(__file__), '..', 'cache')
    return send_from_directory(cache_dir, 'bot.log', as_attachment=True)

@app.route('/api/logs/web', methods=['GET'])
def get_web_logs():
    """ Returns last 200 lines of the webmanager.log file """
    log_path = os.path.join(os.path.dirname(__file__), '..', 'cache', 'webmanager.log')
    if not os.path.exists(log_path):
        return jsonify({'logs': 'Brak logów Web Panelu.'})
    try:
        with open(log_path, 'r', encoding='utf-8') as f:
            lines = f.readlines()
            return jsonify({'logs': ''.join(lines[-200:])})
    except Exception as e:
        return jsonify({'logs': f'Error reading log: {str(e)}'})

@app.route('/bot/start')
def start_bot():
    bm.start()
    return jsonify(bm.is_running())


@app.route('/bot/stop')
def stop_bot():
    bm.stop()
    return jsonify(not bm.is_running())


@app.route('/config', methods=['GET'])
def get_config():
    return render_template('config.html', data=sync(), config=pre_process_config(), helpfile=help_file)


@app.route('/village', methods=['GET'])
def get_village_config():
    data = sync()
    vid = request.args.get("id", None)
    return render_template('village.html', data=data, config=pre_process_village_config(village_id=vid),
                           current_select=vid, helpfile=help_file)


@app.route('/map', methods=['GET'])
def get_map():
    sync_data = sync()
    center_id = request.args.get("center", None)
    center = next(iter(sync_data.get('bot', [])), None) if not center_id else center_id
    map_data = json.dumps(MapBuilder.build(sync_data['villages'], current_village=center, size=15, attacks=sync_data['attacks']))
    return render_template('map.html', data=sync_data, map=map_data)


@app.route('/villages', methods=['GET'])
def get_village_overview():
    return render_template('villages.html', data=sync())


@app.route('/building_templates', methods=['GET', 'POST'])
def get_building_templates():
    if request.form.get('new', None):
        plain = os.path.basename(request.form.get('new'))
        if not plain.endswith('.txt'):
            plain = "%s.txt" % plain
        tempfile = '../templates/builder/%s' % plain
        if not os.path.exists(tempfile):
            with open(tempfile, 'w') as ouf:
                ouf.write("")
    selected = request.args.get('t', None)
    return render_template('templates.html',
                           templates=BuildingTemplateManager.template_cache_list(),
                           selected=selected,
                           buildings=buildings)


@app.route('/', methods=['GET'])
def get_home():
    session = DataReader.get_session()
    return render_template('bot.html', data=sync(), session=session)


@app.route('/app/js', methods=['GET'])
def get_js():
    urlpath = os.path.join(os.path.dirname(__file__), "public")
    return send_from_directory(urlpath, "js.v2.js")


@app.route('/app/config/set', methods=['GET'])
def config_set():
    vid = request.args.get("village_id", None)
    if not vid:
        DataReader.config_set(parameter=request.args.get("parameter"), value=request.args.get("value", None))
    else:
        param = request.args.get("parameter")
        if param.startswith("village."):
            param = param.replace("village.", "")
        DataReader.village_config_set(village_id=vid, parameter=param, value=request.args.get("value", None))

    return jsonify(sync())


@app.route('/api/clear_reports', methods=['POST'])
def clear_reports_endpoint():
    """
    Clears all cached report JSON files and deletes related info.
    Then kicks off historical report scan.
    """
    try:
        cache_dir = os.path.join(os.path.dirname(__file__), '..', 'cache', 'reports')
        if os.path.exists(cache_dir):
            import glob
            files = glob.glob(os.path.join(cache_dir, '*.json'))
            for f in files:
                try:
                    os.remove(f)
                except:
                    pass
        
        # Trigger force_reports
        data = request.get_json(silent=True) or {}
        pages = str(data.get('pages', 5))
        import subprocess
        script_path = os.path.join(os.path.dirname(__file__), '..', 'force_read_reports.py')
        if os.path.exists(script_path):
            subprocess.Popen([sys.executable, script_path, pages], cwd=os.path.join(os.path.dirname(__file__), '..'))
        return jsonify({"ok": True, "message": f"Raporty wyczyszczone! Skan ({pages} stron) pobiera historię od nowa w tle."})
    except Exception as e:
        return jsonify({"ok": False, "message": str(e)}), 500

if len(sys.argv) > 1:
    port = int(sys.argv[1])
else:
    port = int(os.environ.get("FLASK_RUN_PORT", 5000))

host = os.environ.get("FLASK_RUN_HOST", "0.0.0.0")
app.run(host=host, port=port)
