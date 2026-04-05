"""
TWB – Single Entry Point
========================
Uruchamia bota lub restartuje go, jeśli już działa.
Przy pierwszym uruchomieniu (brak konfiguracji) pyta o URL gry.

Użycie:
    python run.py           # uruchom / zrestartuj bota (wizard przy 1. starcie)
    python run.py --status  # pokaż status procesu i wyjdź
    python run.py --stop    # zatrzymaj bota i wyjdź
    python run.py --restart # wymuś restart (nawet jeśli działa)
"""

import argparse
import json
import logging
import os
import signal
import subprocess
import sys
import time

# ---------------------------------------------------------------------------
# Ścieżki
# ---------------------------------------------------------------------------
BASE_DIR   = os.path.dirname(os.path.realpath(__file__))
CACHE_DIR  = os.path.join(BASE_DIR, "cache")
PID_FILE   = os.path.join(CACHE_DIR, "twb.pid")
RUN_LOG    = os.path.join(CACHE_DIR, "run.log")
BOT_LOG    = os.path.join(CACHE_DIR, "bot.log")
CONFIG     = os.path.join(BASE_DIR,  "config.json")
CONFIG_EX  = os.path.join(BASE_DIR,  "config.example.json")
BOT_SCRIPT = os.path.join(BASE_DIR,  "twb.py")

# Preferuj Python z lokalnego venv, fallback na systemowy
_VENV_PYTHON = os.path.join(BASE_DIR, "env", "bin", "python")
PYTHON_BIN   = _VENV_PYTHON if os.path.exists(_VENV_PYTHON) else sys.executable

# Serwer-placeholder z config.example – marker "niekonfigurowalne"
_PLACEHOLDER_SERVER = "nlc1"

# ---------------------------------------------------------------------------
# Logging (konsola + plik)
# ---------------------------------------------------------------------------
os.makedirs(CACHE_DIR, exist_ok=True)

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [run.py] %(levelname)s - %(message)s",
    handlers=[
        logging.StreamHandler(sys.stdout),
        logging.FileHandler(RUN_LOG, encoding="utf-8"),
    ],
)
log = logging.getLogger("run")


# ---------------------------------------------------------------------------
# Helpers – config JSON
# ---------------------------------------------------------------------------

def load_config() -> dict:
    if not os.path.exists(CONFIG):
        if os.path.exists(CONFIG_EX):
            with open(CONFIG_EX, encoding="utf-8") as f:
                return json.load(f)
        return {}
    with open(CONFIG, encoding="utf-8") as f:
        return json.load(f)


def save_config(data: dict) -> None:
    with open(CONFIG, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2, ensure_ascii=False)


def needs_setup(cfg: dict) -> bool:
    """Zwraca True jeśli konfiguracja jest nietkniętym placeholderem."""
    return cfg.get("server", {}).get("server", "") == _PLACEHOLDER_SERVER


# ---------------------------------------------------------------------------
# Wizard pierwszego uruchomienia
# ---------------------------------------------------------------------------

def _separator():
    print("\n" + "─" * 60)


def first_run_wizard(cfg: dict) -> dict:
    """
    Interaktywny kreator konfiguracji.
    Pyta o URL gry i opcjonalne ustawienia, zapisuje config.json.
    """
    _separator()
    print("  ⚔️  TWB – Kreator pierwszego uruchomienia")
    _separator()
    print(
        "\nWitaj! Wygląda na to, że bot nie jest jeszcze skonfigurowany.\n"
        "Odpowiedz na kilka pytań – resztą zajmie się bot.\n"
    )

    # ------------------------------------------------------------------
    # 1. URL gry
    # ------------------------------------------------------------------
    print("── Krok 1/3 – Adres serwera ────────────────────────────")
    print(
        "\nWejdź w grę przez przeglądarkę, skopiuj URL z paska adresu\n"
        "i wklej go tutaj. Powinien wyglądać mniej więcej tak:\n"
        "  https://pl227.plemiona.pl/game.php?village=12345&screen=overview\n"
    )

    game_url = ""
    while True:
        game_url = input("URL gry > ").strip()
        if game_url.lower() in ("q", "quit", "exit"):
            print("Anulowano. Wychodzę.")
            sys.exit(0)
        if game_url.startswith("http") and "game.php" in game_url:
            break
        print(
            "⚠  Niepoprawny URL. Musi zaczynać się od 'https://' "
            "i zawierać 'game.php'. Spróbuj ponownie (lub wpisz 'q' aby wyjść)."
        )

    # Wyciągnij endpoint i server
    try:
        endpoint = game_url.split("?")[0]          # https://pl227.plemiona.pl/game.php
        host     = endpoint.split("//")[1]         # pl227.plemiona.pl/game.php
        server   = host.split(".")[0]              # pl227
    except Exception:
        print("Nie udało się rozpoznać serwera z URL. Spróbuj ponownie.")
        return first_run_wizard(cfg)

    print(f"\n  ✅ Endpoint : {endpoint}")
    print(f"  ✅ Serwer   : {server.upper()}")
    ok = input("\nCzy to wygląda poprawnie? [T/n] > ").strip().lower()
    if ok in ("n", "nie"):
        return first_run_wizard(cfg)

    cfg["server"]["endpoint"] = endpoint
    cfg["server"]["server"]   = server

    # ------------------------------------------------------------------
    # 2. Godziny aktywności
    # ------------------------------------------------------------------
    _separator()
    print("\n── Krok 2/3 – Godziny aktywności ───────────────────────")
    print(
        "\nW jakich godzinach bot ma być aktywny? (format: GG-GG)\n"
        "Poza tym przedziałem bot będzie działać rzadziej.\n"
        "Wciśnij Enter żeby zostawić domyślne (6-23)."
    )
    hours = input("Godziny [6-23] > ").strip()
    if not hours:
        hours = "6-23"
    cfg["bot"]["active_hours"] = hours

    # ------------------------------------------------------------------
    # 3. Panel webowy i rozszerzenie Chrome
    # ------------------------------------------------------------------
    _separator()
    print("\n── Krok 3/3 – Panel webowy i rozszerzenie Chrome ───────")
    print(
        "\nBot ma panel webowy dostępny w przeglądarce (port 5000).\n"
        "Rozszerzenie Chrome automatycznie będzie wysyłać ciasteczka\n"
        "sesji do bota – nie będziesz musiał nic wklejać ręcznie.\n"
    )

    print(
        "Gdzie ma być dostępny panel webowy?\n"
        "\n"
        "  [1] Tylko lokalnie (127.0.0.1) – bezpieczniejsze,\n"
        "      panel dostępny wyłącznie na tym komputerze.\n"
        "\n"
        "  [2] W sieci (0.0.0.0) – panel dostępny z innych\n"
        "      urządzeń w sieci lub przez internet (jeśli port\n"
        "      5000 jest otwarty w firewallu).\n"
    )
    panel_host_choice = ""
    while panel_host_choice not in ("1", "2"):
        panel_host_choice = input("Wybór [1/2] > ").strip()

    if panel_host_choice == "1":
        panel_host = "127.0.0.1"
        panel_url  = "http://127.0.0.1:5000"
        print("\n  ✅ Panel będzie dostępny tylko lokalnie.")
    else:
        panel_host = "0.0.0.0"
        # Wykryj lokalny IP żeby pokazać użytkownikowi właściwy URL
        try:
            import socket
            s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
            s.connect(("8.8.8.8", 80))
            local_ip = s.getsockname()[0]
            s.close()
        except Exception:
            local_ip = "TWÓJ_IP"
        panel_url = f"http://{local_ip}:5000"
        print(f"\n  ✅ Panel będzie dostępny w sieci pod: {panel_url}")

    print(
        "\n  Po uruchomieniu bota zainstaluj rozszerzenie Chrome:\n"
        "  1. Otwórz Chrome → chrome://extensions\n"
        "  2. Włącz 'Tryb dewelopera' (prawy górny róg)\n"
        "  3. Kliknij 'Załaduj rozpakowane' i wskaż folder:\n"
       f"     {os.path.join(BASE_DIR, 'browser_extension')}\n"
        "  4. Otwórz rozszerzenie, wpisz URL bota jako:\n"
       f"     {panel_url}\n"
        "  5. Kliknij 'Save URL', a potem 'Sync now'.\n"
        "  Od tego momentu ciasteczka będą synchronizowane automatycznie.\n"
    )

    cfg["webmanager"]["enabled"] = True
    cfg["webmanager"]["host"]    = panel_host
    cfg["webmanager"]["port"]    = 5000

    _separator()
    print("\n✅ Konfiguracja gotowa! Zapisuję config.json i uruchamiam bota...\n")
    save_config(cfg)
    log.info("Konfiguracja zapisana (server=%s, endpoint=%s).", server, endpoint)
    return cfg


# ---------------------------------------------------------------------------
# Helpers – zarządzanie procesem
# ---------------------------------------------------------------------------

def read_pid() -> int | None:
    if not os.path.exists(PID_FILE):
        return None
    try:
        with open(PID_FILE) as f:
            return int(f.read().strip())
    except (ValueError, OSError):
        return None


def write_pid(pid: int) -> None:
    with open(PID_FILE, "w") as f:
        f.write(str(pid))


def remove_pid() -> None:
    try:
        os.remove(PID_FILE)
    except FileNotFoundError:
        pass


def is_running(pid: int | None) -> bool:
    if pid is None:
        return False
    try:
        import psutil
        return psutil.pid_exists(pid)
    except ImportError:
        try:
            os.kill(pid, 0)
            return True
        except (ProcessLookupError, PermissionError):
            return False


def cleanup_stale_processes():
    """
    Agresywnie czyści stare instancje bota i procesy zajmujące port 5000.
    Zapobiega duplikatom i błędom 'Address already in use'.
    """
    log.info("Sprzątanie starych procesów przed startem...")
    
    # 1. Zabij procesy po PID z pliku (jeśli istnieje)
    old_pid = read_pid()
    if old_pid:
        try:
            import psutil
            if psutil.pid_exists(old_pid):
                proc = psutil.Process(old_pid)
                for child in proc.children(recursive=True):
                    child.terminate()
                proc.terminate()
                log.info("Zabito starą instancję bota (PID %d).", old_pid)
        except Exception:
            pass
        remove_pid()

    # 2. Zabij procesy zajmujące port 5000 (WebManager)
    try:
        import psutil
        for proc in psutil.process_iter(['pid', 'name', 'connections']):
            try:
                for conn in proc.info.get('connections', []):
                    if conn.laddr.port == 5000:
                        log.warning("Wykryto proces (PID %d) zajmujący port 5000. Zabijam go...", proc.info['pid'])
                        proc.kill()
            except (psutil.NoSuchProcess, psutil.AccessDenied):
                continue
    except Exception as e:
        log.debug("Błąd podczas skanowania portów: %s", e)

    # 3. Zabij procesy po nazwie (na wszelki wypadek)
    try:
        import psutil
        current_pid = os.getpid()
        for proc in psutil.process_iter(['pid', 'name', 'cmdline']):
            try:
                cmdline = " ".join(proc.info.get('cmdline', []) or [])
                if ("twb.py" in cmdline or "server.py 5000" in cmdline) and proc.info['pid'] != current_pid:
                    if proc.info['pid'] != old_pid: # unikaj podwójnego logowania tego samego
                        log.warning("Zabijam zagubiony proces bota (PID %d): %s", proc.info['pid'], cmdline)
                        proc.kill()
            except (psutil.NoSuchProcess, psutil.AccessDenied):
                continue
    except Exception:
        pass

    # 4. Usuń plik blokady bota (bot.lock)
    lock_file = os.path.join(CACHE_DIR, "bot.lock")
    if os.path.exists(lock_file):
        try:
            os.remove(lock_file)
            log.info("Usunięto plik blokady bot.lock.")
        except Exception:
            pass


def stop_bot(pid: int, timeout: int = 10) -> None:
    log.info("Zatrzymuję bota (PID %d)...", pid)
    try:
        import psutil
        if psutil.pid_exists(pid):
            proc = psutil.Process(pid)
            # Zabij dzieci (WebManager)
            for child in proc.children(recursive=True):
                child.terminate()
            proc.terminate()
            
            # Czekaj na zakończenie
            gone, alive = psutil.wait_procs([proc] + proc.children(), timeout=timeout)
            for p in alive:
                p.kill()
    except Exception:
        # Fallback do prostego os.kill jeśli brak psutil
        try:
            os.kill(pid, signal.SIGTERM)
            time.sleep(2)
            os.kill(pid, signal.SIGKILL)
        except Exception:
            pass
    
    remove_pid()
    log.info("Bot zatrzymany.")


def start_bot() -> int:
    # Upewnij się że nie ma śmieci przed startem
    cleanup_stale_processes()
    
    bot_log_f = open(BOT_LOG, "a", encoding="utf-8")
    proc = subprocess.Popen(
        [PYTHON_BIN, BOT_SCRIPT],
        cwd=BASE_DIR,
        stdout=bot_log_f,
        stderr=bot_log_f,
        stdin=subprocess.DEVNULL,   # bot działa headless; ciasteczka przez rozszerzenie
        start_new_session=True,     # odłącz od bieżącej sesji terminala
    )
    bot_log_f.close()
    write_pid(proc.pid)
    log.info("Bot uruchomiony (PID %d). Logi: %s", proc.pid, BOT_LOG)
    return proc.pid


# ---------------------------------------------------------------------------
# Punkt wejścia
# ---------------------------------------------------------------------------

def main() -> None:
    parser = argparse.ArgumentParser(description="TWB – Punkt startowy bota Plemion")
    parser.add_argument("--status",   action="store_true", help="Pokaż status i wyjdź.")
    parser.add_argument("--stop",     action="store_true", help="Zatrzymaj bota i wyjdź.")
    parser.add_argument("--restart",  action="store_true", help="Wymuś restart.")
    parser.add_argument("--reconfig", action="store_true", help="Uruchom kreator konfiguracji od nowa (nawet jeśli bot jest już skonfigurowany).")
    args = parser.parse_args()

    pid = read_pid()

    # -- STATUS --
    if args.status:
        if pid and is_running(pid):
            log.info("✅ Bot DZIAŁA (PID %d).", pid)
        else:
            log.info("❌ Bot NIE działa.")
            if pid:
                remove_pid()
        sys.exit(0)

    # -- STOP --
    if args.stop:
        if pid and is_running(pid):
            stop_bot(pid)
        else:
            log.info("Bot nie działa – nic do zatrzymania.")
            remove_pid()
        sys.exit(0)

    # -- WIZARD przy pierwszym lub wymuszonym uruchomieniu --
    cfg = load_config()
    if args.reconfig:
        log.info("Tryb rekonfiguracji – uruchamiam kreator od nowa.")
        # Zatrzymaj bota jeśli działa, żeby uniknąć konfliktu
        if pid and is_running(pid):
            log.info("Zatrzymuję działającego bota przed rekonfiguracją...")
            stop_bot(pid)
            pid = None
            time.sleep(1)
        cfg = first_run_wizard(cfg)
    elif needs_setup(cfg):
        cfg = first_run_wizard(cfg)

    # -- START / RESTART --
    if pid and is_running(pid):
        log.info("Bot już działa (PID %d) – restartuję...", pid)
        stop_bot(pid)

    time.sleep(1)

    new_pid = start_bot()

    # Krótka weryfikacja – czy bot przeżył pierwsze 2 sekundy
    time.sleep(2)
    if not is_running(new_pid):
        log.error(
            "❌ Bot zakończył się natychmiast po starcie!\n"
            "   Sprawdź logi: %s",
            BOT_LOG,
        )
        remove_pid()
        sys.exit(1)

    print(
        "\n" + "─" * 60 +
        "\n  Bot działa w tle. Co dalej:\n"
        f"  • Logi bota  : {BOT_LOG}\n"
        f"  • Panel web  : http://localhost:5000\n"
        f"  • Status     : python run.py --status\n"
        f"  • Zatrzymaj  : python run.py --stop\n" +
        "─" * 60 + "\n"
    )

    log.info(
        "Jeśli to pierwsze uruchomienie: otwórz przeglądarkę\n"
        "   i skorzystaj z rozszerzenia Chrome żeby wysłać ciasteczka.\n"
        "   Bot czeka na sesję – bez niej nie rozpocznie pracy."
    )


if __name__ == "__main__":
    main()
