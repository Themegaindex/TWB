"""
Class for using one generic cookie jar, emulating a single tab
"""

import requests

from core.filemanager import FileManager
from core.notification import Notification

import logging
import re
import time
import random
import os
from urllib.parse import urljoin, urlencode

from core.reporter import ReporterObject
from core.database import DatabaseManager, DBSession


class WebWrapper:
    """
    WebWrapper object for sending HTTP requests
    """
    web = None
    headers = {
        'user-agent': 'Mozilla/5.0 (Windows NT 6.3; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/78.0.3904.97 Safari/537.36',
        'upgrade-insecure-requests': '1'
    }
    endpoint = None
    logger = logging.getLogger("Requests")
    server = None
    last_response = None
    last_h = None
    priority_mode = False
    auth_endpoint = None
    reporter = None
    delay = 1.0

    def __init__(self, url, server=None, endpoint=None, reporter_enabled=False, reporter_constr=None):
        """
        Construct the session and detect variables
        """
        self.web = requests.session()
        self.auth_endpoint = url
        self.server = server
        self.endpoint = endpoint
        self.reporter = ReporterObject(enabled=reporter_enabled, connection_string=reporter_constr)

    def post_process(self, response):
        """
        Post-processes all requests and stores data used for the next request
        """
        xsrf = re.search('<meta content="(.+?)" name="csrf-token"', response.text)
        if xsrf:
            self.headers['x-csrf-token'] = xsrf.group(1)
            self.logger.debug("Set CSRF token")
        elif 'x-csrf-token' in self.headers:
            del self.headers['x-csrf-token']
        self.headers['Referer'] = response.url
        self.last_response = response
        get_h = re.search(r'&h=(\w+)', response.text)
        if get_h:
            self.last_h = get_h.group(1)

    def get_url(self, url, headers=None):
        """
        Fetches a URL using a basic GET request
        """
        self.headers['Origin'] = (self.endpoint if self.endpoint else self.auth_endpoint).rstrip('/')
        if not self.priority_mode:
            time.sleep(random.randint(int(3 * self.delay), int(7 * self.delay)))
        url = urljoin(self.endpoint if self.endpoint else self.auth_endpoint, url)
        if not headers:
            headers = self.headers
        try:
            res = self.web.get(url=url, headers=headers, timeout=30)
            self.logger.debug("GET %s [%d]", url, res.status_code)
            self.post_process(res)
            
            # Enhanced bot/security detection patterns
            bot_patterns = [
                'data-bot-protect', 
                'screen=bot_protect', 
                'bot_protection', 
                'captcha', 
                'security_check',
                'p_sid_bot',
                'id="bot_check"',
                'bot_check',
                'Weryfikacja bota',
                'Weryfikacja gracza',
                'Bot-Schutz',
                'confirm_captcha',
                'p_sid_bot'
            ]
            
            if any(p in res.text for p in bot_patterns):
                self.logger.warning("Bot protection (captcha) hit! Page: %s", res.url)
                self.reporter.report(
                    0, "TWB_RECAPTCHA", "Stopping bot, solve the captcha in browser and resume.")
                Notification.send("Bot protection hit! Solve captcha.")
                
                import sys
                if sys.stdin.isatty():
                    input("Solve the captcha in your browser and then press ENTER here to continue...")
                    return self.get_url(url, headers)
                else:
                    self.logger.error("Non-interactive mode: cannot wait for captcha solution. Stopping.")
                    # Return response so caller can see the screen type but we shouldn't continue
                    return res
            return res
        except Exception as e:
            self.logger.warning("GET %s: %s", url, str(e))
            return None

    def post_url(self, url, data, headers=None):
        """
        Sends a basic POST request with urlencoded postdata
        """
        if not self.priority_mode:
            time.sleep(
                random.randint(int(3 * self.delay), int(7 * self.delay))
            )
        self.headers['Origin'] = (self.endpoint if self.endpoint else self.auth_endpoint).rstrip('/')
        url = urljoin(self.endpoint if self.endpoint else self.auth_endpoint, url)
        enc = urlencode(data)
        if not headers:
            headers = self.headers
        try:
            res = self.web.post(url=url, data=data, headers=headers, timeout=30)
            self.logger.debug("POST %s %s [%d]", url, enc, res.status_code)
            self.post_process(res)
            return res
        except Exception as e:
            self.logger.warning("POST %s %s: %s", url, enc, str(e))
            return None

    def set_cookies(self, cookies: dict):
        """
        Manually inject cookies into headers bypassing requests jar mutating pl_auth
        """
        cookie_str = "; ".join([f"{k}={v}" for k, v in cookies.items()])
        for k, v in cookies.items():
            if k == "Cookie":
                cookie_str = v
                break
        self.headers['Cookie'] = cookie_str
        self.web.cookies.clear()
        
    def start(self, ):
        """
        Start the bot and verify whether the last session is still valid
        """
        session_data = None
        db_s = DatabaseManager._session()
        if db_s:
            try:
                row = db_s.query(DBSession).order_by(DBSession.updated_at.desc()).first()
                if row and row.cookies:
                    session_data = {
                        "endpoint": row.endpoint,
                        "server": row.server,
                        "cookies": row.cookies,
                        "user_agent": row.user_agent
                    }
            except Exception as e:
                self.logger.error(f"Error reading session from DB: {e}")
            finally:
                db_s.close()
            
        if session_data:
            import urllib.parse
            # Set cookies explicitly decoding url encodings
            if session_data.get('endpoint'):
                ep = session_data['endpoint']
                forbidden_servers = ["www", "plemiona", "tribalwars", "die-staemme"]
                try:
                    extracted_server = ep.split("//")[1].split(".")[0]
                    if extracted_server not in forbidden_servers and len(extracted_server) > 0:
                        self.endpoint = ep
                        self.server = extracted_server
                except Exception:
                    pass
            self.set_cookies(session_data['cookies'])
            get_test = self.get_url("game.php?screen=overview")
            if get_test and "game.php" in get_test.url:
                return True
            self.logger.warning("Current database session not valid")
            # Clear invalid session in DB
            db_s = DatabaseManager._session()
            if db_s:
                try:
                    db_s.query(DBSession).delete()
                    db_s.commit()
                except Exception:
                    db_s.rollback()
                finally:
                    db_s.close()

        self.web.cookies.clear()
        print("Waiting for browser cookie... (Use the Chrome Extension to sync automatically or paste the string here and press Enter)")
        
        import sys
        import select
        import time
        cinp = ""
        while True:
            # Check if Web Panel filled the DB session in the background
            db_s = DatabaseManager._session()
            if db_s:
                try:
                    row = db_s.query(DBSession).order_by(DBSession.updated_at.desc()).first()
                    if row and row.cookies:
                        session_data = {
                            "endpoint": row.endpoint,
                            "server": row.server,
                            "cookies": row.cookies,
                            "user_agent": row.user_agent
                        }
                    else:
                        session_data = None
                except Exception:
                    session_data = None
                finally:
                    db_s.close()
            else:
                session_data = None
                
            if session_data and "cookies" in session_data and session_data["cookies"]:
                if session_data.get("endpoint"):
                    ep = session_data["endpoint"]
                    forbidden_servers = ["www", "plemiona", "tribalwars", "die-staemme"]
                    try:
                        extracted_server = ep.split("//")[1].split(".")[0]
                        if extracted_server not in forbidden_servers and len(extracted_server) > 0:
                            self.endpoint = ep
                            self.server = extracted_server
                    except Exception:
                        pass
                
                # Update User Agent from Browser
                if session_data.get("user_agent"):
                    self.headers["user-agent"] = session_data["user_agent"]
                    try:
                        import json
                        conf = FileManager.load_json_file("config.json")
                        conf["bot"]["user_agent"] = session_data["user_agent"]
                        FileManager.save_json_file(conf, "config.json")
                    except Exception:
                        pass
                # Load cookies into request session carefully handling url decoding
                import urllib.parse
                # Set raw Cookie String header to avoid `requests` mutating pl_auth characters
                cookie_str = "; ".join([f"{k}={v}" for k, v in session_data['cookies'].items()])
                for k, v in session_data['cookies'].items():
                    if k == "Cookie":
                        cookie_str = v
                        break
                self.headers["Cookie"] = cookie_str
                
                get_test_url = urljoin(self.endpoint, "game.php?screen=overview")
                try:
                    # Use requests directly instead of urllib to avoid global side effects
                    self.logger.debug(f"Verifying DB session cookies at: {get_test_url}")
                    
                    # Create temporary cookies dict for verification
                    test_headers = dict(self.headers)
                    test_headers["Cookie"] = cookie_str
                    
                    res_test = self.web.get(get_test_url, headers=test_headers, allow_redirects=False, timeout=10)
                    
                    if getattr(self, "logger", None):
                        self.logger.info(f"Loaded {len(session_data['cookies'])} cookies from Web Panel!")
                    
                    # 200 means we stayed on the overview page (logged in)
                    # 302 to index.php or similar means we are not logged in
                    if res_test.status_code == 200:
                        self.logger.info("Found synced cookies from DB! Login successful.")
                        # Transfer verified cookies to main session
                        self.headers["Cookie"] = cookie_str
                        self.web.cookies.clear()
                        return True
                    else:
                        self.logger.warning(f"Cookies from DB are invalid. Server returned status {res_test.status_code}")
                        db_s = DatabaseManager._session()
                        if db_s:
                            try:
                                db_s.query(DBSession).delete()
                                db_s.commit()
                            except Exception:
                                db_s.rollback()
                            finally:
                                db_s.close()
                except Exception as e:
                    self.logger.warning(f"Error during verify DB credentials: {e}")
                    db_s = DatabaseManager._session()
                    if db_s:
                        try:
                            db_s.query(DBSession).delete()
                            db_s.commit()
                        except Exception:
                            db_s.rollback()
                        finally:
                            db_s.close()
                
            # Sprawdź bez blokowania wstrzymania dla wejścia z klawiatury (max 1 sekunda na cykl).
            # Gdy bot uruchomiony bez TTY (nohup/subprocess), select() rzuca OSError –
            # ignorujemy to i czekamy na ciastka z bazy danych.
            try:
                if sys.stdin.fileno() >= 0 and sys.stdin in select.select([sys.stdin], [], [], 1.0)[0]:
                    cinp = sys.stdin.readline().strip()
                    if cinp:
                        # Ktoś wpisał własne ręczne ciastko
                        break
            except (OSError, ValueError):
                # Brak TTY – działamy w trybie headless, czekamy na ciastka z DB
                time.sleep(1)

        cookies = {}
        for itt in cinp.split(';'):
            itt = itt.strip()
            kvs = itt.split("=")
            if len(kvs) > 1:
                k = kvs[0]
                v = '='.join(kvs[1:])
                cookies[k] = v
        self.web.cookies.update(cookies)
        self.logger.info("Game Endpoint: %s", self.endpoint)

        for c in self.web.cookies:
            cookies[c.name] = c.value

        db_s = DatabaseManager._session()
        if db_s:
            try:
                # Remove old sessions
                db_s.query(DBSession).delete()
                # Insert new session
                new_sess = DBSession(
                    endpoint=self.endpoint,
                    server=self.server,
                    cookies=cookies,
                    user_agent=self.headers.get('user-agent')
                )
                db_s.add(new_sess)
                db_s.commit()
            except Exception as e:
                self.logger.error(f"Failed to manually save keyboard session to DB: {e}")
                db_s.rollback()
            finally:
                db_s.close()

        return True

    def get_action(self, village_id, action):
        """
        Runs an action on a specific village
        """
        url = "game.php?village=%s&screen=%s" % (village_id, action)
        response = self.get_url(url)
        return response

    def _parse_api_response(self, response, context):
        """Return parsed JSON data for API requests when possible."""
        if response is None:
            self.logger.warning("No response received for %s", context)
            return None
        if response.status_code != 200:
            return None
        try:
            return response.json()
        except ValueError:
            return response

    def get_api_data(self, village_id, action, params={}):

        custom = dict(self.headers)
        custom['accept'] = "application/json, text/javascript, */*; q=0.01"
        custom['x-requested-with'] = "XMLHttpRequest"
        custom['tribalwars-ajax'] = "1"
        req = {
            'ajax': action,
            'village': village_id,
            'screen': 'api'
        }
        req.update(params)
        payload = f"game.php?{urlencode(req)}"
        url = urljoin(self.endpoint, payload)
        res = self.get_url(url, headers=custom)
        return self._parse_api_response(
            res,
            f"get_api_data(action={action}, village={village_id})",
        )

    def post_api_data(self, village_id, action, params={}, data={}):
        """
        Simulates an API request
        """
        custom = dict(self.headers)
        custom['accept'] = "application/json, text/javascript, */*; q=0.01"
        custom['x-requested-with'] = "XMLHttpRequest"
        custom['tribalwars-ajax'] = "1"
        req = {
            'ajax': action,
            'village': village_id,
            'screen': 'api'
        }
        req.update(params)
        payload = f"game.php?{urlencode(req)}"
        url = urljoin(self.endpoint, payload)
        if 'h' not in data:
            data['h'] = self.last_h
        res = self.post_url(url, data=data, headers=custom)
        return self._parse_api_response(
            res,
            f"post_api_data(action={action}, village={village_id})",
        )

    def get_api_action(self, village_id, action, params={}, data={}):
        """
        Simulates an API action being triggered
        """
        custom = dict(self.headers)
        custom['Accept'] = "application/json, text/javascript, */*; q=0.01"
        custom['X-Requested-With'] = "XMLHttpRequest"
        custom['TribalWars-Ajax'] = "1"
        req = {
            'ajaxaction': action,
            'village': village_id,
            'screen': 'api'
        }
        req.update(params)
        payload = f"game.php?{urlencode(req)}"
        url = urljoin(self.endpoint, payload)
        if 'h' not in data:
            data['h'] = self.last_h
        res = self.post_url(url, data=data, headers=custom)
        return self._parse_api_response(
            res,
            f"get_api_action(action={action}, village={village_id})",
        )
