import sys
import os
import requests
import urllib.parse
import json
from datetime import datetime

# Dodajemy bieżący katalog do ścieżki, aby móc importować moduły TWB
sys.path.append(os.path.abspath("."))

from core.database import DBSession, get_engine
from core.filemanager import FileManager
from sqlalchemy.orm import sessionmaker

def get_latest_session():
    """Pobiera najnowszą sesję bota z bazy danych."""
    engine = get_engine()
    Session = sessionmaker(bind=engine)
    s = Session()
    try:
        # Pobieramy najnowszą aktywną sesję
        row = s.query(DBSession).order_by(DBSession.updated_at.desc()).first()
        if row:
            return {
                "endpoint": row.endpoint,
                "cookies": row.cookies,
                "user_agent": row.user_agent,
                "server": row.server
            }
    except Exception as e:
        print(f"Błąd bazy danych: {e}")
    finally:
        s.close()
    return None

def sync_twm():
    print("--- TribalWarsMap Sync Script ---")
    sess_data = get_latest_session()
    
    if not sess_data:
        print("BŁĄD: Nie znaleziono aktywnej sesji bota w bazie danych.")
        print("Uruchom bota i zaloguj się w panelu WWW, aby odświeżyć ciastka.")
        return

    # 1. Przygotowanie sesji HTTP
    s = requests.Session()
    ua = sess_data.get('user_agent', 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36')
    s.headers.update({
        'User-Agent': ua,
        'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,*/*;q=0.8',
        'Accept-Language': 'pl,en-US;q=0.7,en;q=0.3',
        'Upgrade-Insecure-Requests': '1'
    })
    
    # Wstrzykujemy ciastka Plemion (plemiona.pl)
    tw_domain = urllib.parse.urlparse(sess_data['endpoint']).netloc
    for k, v in sess_data['cookies'].items():
        s.cookies.set(k, v, domain=tw_domain)
    
    # 2. Określenie URL mapy
    world = sess_data['server']
    twm_url = f"https://{world}.tribalwarsmap.com/pl/"
    
    print(f"Próba logowania na: {twm_url}")
    print(f"Używam serwera: {world}")
    print(f"Używam User-Agent: {ua}")

    # 3. Sprawdź czy już jesteśmy zalogowani
    try:
        res = s.get(twm_url, timeout=15)
        if "Wyloguj" in res.text or "Logout" in res.text:
            print("INFO: Już jesteś zalogowany na TribalWarsMap!")
            save_cookies(s.cookies, world)
            return

        # 4. Inicjacja procesu OAuth
        # Link do logowania to zazwyczaj /auth/login/
        login_init_url = f"https://{world}.tribalwarsmap.com/auth/login/"
        print(f"Podążam za ścieżką OAuth: {login_init_url}")
        
        # Requests automatycznie podąży za przekierowaniami:
        # TWM -> Plemiona (Authorizuj) -> TWM (Callback)
        res = s.get(login_init_url, allow_redirects=True, timeout=20)
        
        if "Wyloguj" in res.text or "Logout" in res.text:
            print("SUKCES: Zalogowano pomyślnie na TribalWarsMap!")
            save_cookies(s.cookies, world)
        elif "Autoryzuj aplikację" in res.text or "Authorize application" in res.text:
            print("Wymagana ręczna akcja: Strona InnoGames prosi o potwierdzenie autoryzacji.")
            print("Zazwyczaj bot nie może tego kliknąć automatycznie za pierwszym razem.")
            print(f"Spróbuj wejść w przeglądarce (z tymi samymi ciastkami) na: {res.url}")
        else:
            print("NIEPOWODZENIE: Nie udało się zalogować automatycznie.")
            print(f"Ostatni URL: {res.url}")
            # print(f"Treść strony (skrót): {res.text[:500]}")

    except Exception as e:
        print(f"Wystąpił błąd podczas komunikacji: {e}")

def save_cookies(cookie_jar, server):
    """Zapisuje ciastka do pliku JSON dla użytkownika."""
    cookies_dict = {}
    for cookie in cookie_jar:
        if "tribalwarsmap.com" in cookie.domain:
            cookies_dict[cookie.name] = cookie.value
    
    filename = f"twm_cookies_{server}.json"
    with open(filename, "w") as f:
        json.dump(cookies_dict, f, indent=4)
    
    print(f"INFO: Ciastka dla TribalWarsMap zostały zapisane w: {filename}")
    print("Możesz ich teraz użyć w innych skryptach.")

if __name__ == "__main__":
    sync_twm()
