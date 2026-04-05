# DEV_NOTES.md – TWB AI-Update Branch
> Wygenerowano: 2026-03-26 | Autor analizy: Antigravity AI
> Gałąź: `AI-Update` | Repo: https://github.com/JakubPisula/TWB

---

## 1. Stan Projektu – Podsumowanie

Bot TWB przeszedł znaczącą migrację z przechowywania danych w plikach JSON (cache/*.json) na PostgreSQL + SQLAlchemy ORM. Dodano również synchronizację ciasteczek przez rozszerzenie do Chrome oraz panel webowy (Flask). Zmiany są architektonicznie słuszne, ale implementacja zawiera szereg błędów krytycznych i technicznych, które opisuję poniżej.

---

## 2. Błędy Krytyczne (Naprawić Natychmiast)

### BUG-01: OSError przy starcie bez TTY
**Plik:** `core/request.py`, linia ~287
**Status:** NAPRAWIONY w tym kroku

Bot był uruchamiany przez `subprocess.Popen(..., stdin=subprocess.DEVNULL)`, co powodowało `OSError: [Errno 9] Bad file descriptor`. Bot crashował 3 razy i wychodził.
**Naprawa:** Dodano `try/except (OSError, ValueError)` z fallbackiem `time.sleep(1)`.

---

### BUG-02: Bot crashuje gdy baza PostgreSQL jest niedostępna przy starcie
**Plik:** `core/database.py`, linia ~476 (bootstrap przy imporcie)
**Status:** CZĘŚCIOWO OBSŁUŻONY – `try/except` jest, ale brak retry logic

`get_engine()` jest wywoływany przy imporcie modułu. Jeśli baza nie jest jeszcze gotowa (Docker wciąż startuje), moduł loguje ostrzeżenie ale `_engine` pozostaje `None`. Problem: każde kolejne wywołanie `get_session()` bede próbować połączyć się na nowo – co może prowadzić do kaskady błędów jeśli baza nadal nie jest dostępna.
**Zalecenie:** Dodać retry z wykładniczym backoff (np. 5 prób z 2s, 4s, 8s...).

---

### BUG-03: Duplikat SQLAlchemy w requirements.txt
**Plik:** `requirements.txt`
**Status:** NAPRAWIONY w tym kroku

Dwa wpisy: `sqlalchemy` (bez wersji) i `SQLAlchemy>=2.0.0`.

---

### BUG-04: Brak obsługi `get_test.url` gdy `get_test` jest `None`
**Plik:** `core/request.py`, linia ~163
**Status:** NIE NAPRAWIONY

```python
get_test = self.get_url("game.php?screen=overview")
if "game.php" in get_test.url:  # AttributeError jesli get_test = None!
```
`get_url()` zwraca `None` przy wyjątku (timeout, brak internetu).
**Naprawa:**
```python
if get_test and "game.php" in get_test.url:
```

---

### BUG-05: `pre_process_village_config` używa `.keys()[0]` (Python 2 relikt)
**Plik:** `webmanager/server.py`, linia ~148
**Status:** NIE NAPRAWIONY

```python
config = config[config.keys()[0]]  # TypeError w Python 3!
```
**Naprawa:**
```python
config = config[next(iter(config.keys()))]
```

---

### BUG-06: `webmanager/server.py` ma `app.run()` na poziomie modułu
**Plik:** `webmanager/server.py`, linia ~554
**Status:** NIE NAPRAWIONY

`app.run(host=host, port=port)` jest poza blokiem `if __name__ == "__main__":`. Każdy import modułu uruchamia serwer Flask.
**Naprawa:** Przenieść do `if __name__ == "__main__":`.

---

### BUG-07: `manager.py` otwiera config.json bezpośrednio przez `open()`
**Plik:** `manager.py`, linia ~14
**Status:** NIE NAPRAWIONY

```python
with open("config.json", "r") as f:  # zalezy od CWD
```
**Naprawa:**
```python
from core.filemanager import FileManager
config = FileManager.load_json_file("config.json")
```

---

## 3. Luki w Bezpieczeństwie

### SEC-01: CORS ustawiony na `*` (wildcard)
**Plik:** `webmanager/server.py`, linia ~26
```python
CORS(app, resources={r"/*": {"origins": "*"}})
```
Każda strona w przeglądarce może wysyłać zapytania API do bota gdy panel jest publiczny.
**Zalecenie:** Ograniczyć do localhost lub konkretnego IP.

---

### SEC-02: Brak autentykacji na endpointach `/api/cookie_webhook` i `/bot/start`
Każdy kto zna adres IP może wstrzyknąć fałszywe ciasteczka lub zatrzymać/uruchomić bota.
**Zalecenie:** Dodać prosty token API (Bearer token w nagłówku).

---

### SEC-03: Hasła bazy w plikach konfiguracyjnych bez szyfrowania
**Pliki:** `config.json`, `docker-compose.yml`
**Zalecenie:** Przenieść do pliku `.env` i dodać do `.gitignore`.

---

### SEC-04: DEBUG=True w Flask w trybie produkcyjnym
**Plik:** `webmanager/server.py`, linia ~27
```python
app.config["DEBUG"] = True
```
Włączony debugger Flask wystawia interaktywną konsolę Pythona w przypadku błędu.
**Naprawa:** Ustawić `DEBUG=False` lub czytać ze zmiennej środowiskowej `FLASK_DEBUG`.

---

## 4. Problemy Architektoniczne

### ARCH-01: Dwa źródła prawdy dla raportów (JSON + PostgreSQL)
Bot zapisuje raporty do `cache/reports/*.json` (stary system) **i** do tabeli `reports` w PostgreSQL (nowy). Panel webowy nadal czyta pliki JSON przez `DataReader.cache_grab("reports")`. Ryzyko rozjazdu danych.
**Zalecenie:** Wybrać jedno źródło. Rekomendacja: PostgreSQL, `DataReader` powinien czytać z bazy.

---

### ARCH-02: `core/database.py` inicjalizuje engine przy imporcie
Każdy moduł importujący `from core.database import ...` powoduje próbę połączenia z bazą. Utrudnia testowanie i cold-start.
**Zalecenie:** Lazy initialization – inicjalizuj silnik dopiero przy pierwszym użyciu, nie przy imporcie.

---

### ARCH-03: Brak warstwy DAL (Data Access Layer)
`webmanager/server.py` bezpośrednio wywołuje `DatabaseManager._session()` i wykonuje zapytania SQL.
**Zalecenie:** Cały dostęp do danych powinien przechodzić przez `DatabaseManager`.

---

### ARCH-04: Smieci testowe w katalogu głównym
**Pliki:** `test.py`, `test2.py`, `test3.py`, `test4.py`, `test5.py`, `test6.py`, `test7.py` (7 plików!)
Powinny być w `tests/` lub usunięte.

---

### ARCH-05: Katalog `TWB/` (podwójne zagnieżdżenie)
W `root` istnieje `TWB/TWB/` – prawdopodobnie pozostałość po próbie klonowania. Wymaga sprawdzenia i oczyszczenia.

---

### ARCH-06: Folder `Antropic/` w repozytorium
Zawiera prawdopodobnie notatki z sesji Claude. Nie powinien trafiać do repozytorium – dodać do `.gitignore`.

---

## 5. Problemy Jakości Kodu

### QUAL-01: User-Agent zakodowany na stałe i przestarzały
`core/request.py` linia ~27: Chrome 78 z 2019 roku – mocno rozpoznawalna jako bot.

### QUAL-02: `input()` w środku pętli sieciowej
`core/request.py` linia ~85: Przy bot-protection wywoływane jest `input()` – blokuje bota headless na zawsze.

### QUAL-03: Duplikacja kodu weryfikacji cookie
Logika wczytywania ciasteczek z bazy zduplikowana w 3 miejscach w `core/request.py`. Powinna być wydzielona do `_load_session_from_db()`.

### QUAL-04: Mieszanie `urllib.request` z biblioteką `requests`
`core/request.py` linia ~239: Klasa oparta o `requests` używa `urllib.request` do weryfikacji. Niespójność.

### QUAL-05: Brak systemu migracji schematu (Alembic)
`Base.metadata.create_all()` nie obsługuje zmian w istniejącym schemacie. Przy każdej zmianie modelu ORM trzeba ręcznie migrować bazę.
**Zalecenie:** Dodać `alembic` do projektu.

---

## 6. Mapa Drogowa (Roadmap)

### Faza 1 – Stabilizacja (Priorytet: Krytyczny)
| ID | Zadanie | Plik |
|----|---------|------|
| F1-1 | Naprawic `get_test.url` NoneType crash | `core/request.py:163` |
| F1-2 | Naprawic `config.keys()[0]` w webmanager | `webmanager/server.py:148` |
| F1-3 | Przeniesc `app.run()` do `__main__` | `webmanager/server.py:554` |
| F1-4 | Naprawic odczyt config w `manager.py` | `manager.py:14` |
| F1-5 | Dodać retry logic do DB engine | `core/database.py:get_engine()` |
| F1-6 | Dodać `wait-for-db` do `run.py` | `run.py` |

### Faza 2 – Bezpieczeństwo (Priorytet: Wysoki)
| ID | Zadanie | Plik |
|----|---------|------|
| F2-1 | Wylaczyc Flask DEBUG w produkcji | `webmanager/server.py` |
| F2-2 | Dodac token API do endpointow | `webmanager/server.py` |
| F2-3 | Ograniczyc CORS do localhost | `webmanager/server.py` |
| F2-4 | Przeniesc hasla do `.env` | `config.json`, `docker-compose.yml` |

### Faza 3 – Unifikacja Danych (Priorytet: Sredni)
| ID | Zadanie | Opis |
|----|---------|------|
| F3-1 | Wybrac jedno zrodlo danych dla raportow | PostgreSQL jako master |
| F3-2 | Przepisac `DataReader` na odczyt z Postgres | `webmanager/utils.py` |
| F3-3 | Dodac Alembic do migracji schematu | Nowy modul |
| F3-4 | Przenosic logike sesji cookie do DAL | `core/database.py` |

### Faza 4 – Porzadek (Priorytet: Niski)
| ID | Zadanie | Opis |
|----|---------|------|
| F4-1 | Usunac `test*.py` z katalogu glownego | Przeniesc do `tests/` lub usunac |
| F4-2 | Sprawdzic i usunac katalog `TWB/TWB/` | Podwojne zagniezdenie |
| F4-3 | Dodac `Antropic/` do `.gitignore` | Notatki AI nie w repo |
| F4-4 | Ujednolicic uzywanie bibliotek HTTP | Tylko `requests` |
| F4-5 | Refaktoryzacja duplikatu kodu cookie | `core/request.py` |

---

## 7. Pliki Wymagające Natychmiastowej Uwagi

| Priorytet | Plik | Problemy |
|-----------|------|----------|
| KRYTYCZNY | `core/request.py` | BUG-01 (napr.), BUG-04, QUAL-02, QUAL-03, QUAL-04 |
| KRYTYCZNY | `webmanager/server.py` | BUG-05, BUG-06, SEC-01, SEC-02, SEC-04 |
| WYSOKI | `core/database.py` | BUG-02, ARCH-02, QUAL-05 |
| WYSOKI | `manager.py` | BUG-07 |
| SREDNI | `webmanager/utils.py` | ARCH-01, ARCH-03 |
| NISKI | `test*.py` (x7) | ARCH-04 |

---

## 8. Nowe Pliki Dodane w Tym Kroku

| Plik | Opis |
|------|------|
| `run.py` | Nowy punkt startowy bota z zarzadzaniem procesem |
| `DEV_NOTES.md` | Ten plik |

### Uzycie `run.py`:
```bash
# Uruchom bota (lub zrestartuj jesli dziala):
python run.py

# Sprawdz status:
python run.py --status

# Zatrzymaj bota:
python run.py --stop

# Wymuszony restart:
python run.py --restart
```

---

## 9. Uwagi dotyczące Konfiguracji Docker

Aktualny `docker-compose.yml` uzywa `postgres:16` (zmienione z `latest`).
PostgreSQL 18+ zmienilo strukture katalogow danych – uzywaj zawsze konkretnej wersji, nigdy `latest`.

Porty serwisow:
| Serwis | Port | Dostep |
|--------|------|--------|
| PostgreSQL | 5432 | Bot |
| pgAdmin | 5050 | http://localhost:5050 |
| Adminer | 8080 | http://localhost:8080 |
| Portainer | 9000 | http://localhost:9000 |
| Panel Webowy (Flask) | 5000 | http://localhost:5000 |

Dane dostepu do pgAdmin/Adminer:
- Login: `admin@twb.local`, Haslo: `admin_password`
- Baza: host=`twb_postgres` (nazwa kontenera), user=`twb_user`, haslo=`twb_password`, db=`twb_db`
