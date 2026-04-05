import asyncio
import os
import json
import logging
import urllib.parse
from io import BytesIO

import pandas as pd
import httpx
from sqlalchemy.ext.asyncio import create_async_engine
from sqlalchemy import Table, Column, Integer, String, MetaData, func, DateTime, Float, Boolean
from sqlalchemy.dialects.postgresql import insert

# Konfiguracja logowania
logging.basicConfig(level=logging.INFO, format='%(asctime)s [%(levelname)s] %(message)s')
logger = logging.getLogger(__name__)

# Wczytanie config.json bota (zakładamy wywołanie z roota projektu)
CONFIG_PATH = os.path.join(os.path.dirname(__file__), "config.json")
try:
    with open(CONFIG_PATH, "r", encoding="utf-8") as f:
        config = json.load(f)
        server_cfg = config.get("server", {})
        raw_endpoint = server_cfg.get("endpoint", "https://pl227.plemiona.pl/game.php")
        # Wyciągamy sam bazowy URL usuwając /game.php
        endpoint = raw_endpoint.replace("/game.php", "")
        db_cfg = config.get("database", {})
except Exception as e:
    logger.error(f"Nie znaleziono pliku '{CONFIG_PATH}' lub błąd: {e}")
    endpoint = "https://pl227.plemiona.pl"
    db_cfg = {}

# String polaczenia z asynchronicznym DB
db_url_cfg = db_cfg.get("url", "postgresql://twb_user:twb_password@127.0.0.1:5432/twb_db")
if "asyncpg" not in db_url_cfg:
    POSTGRES_URL = db_url_cfg.replace("postgresql://", "postgresql+asyncpg://")
else:
    POSTGRES_URL = db_url_cfg

engine = create_async_engine(POSTGRES_URL, echo=False)
metadata = MetaData()

# Zdefiniowanie modeli zgodnie z core.models

players_table = Table("players", metadata,
    Column("id", String, primary_key=True),
    Column("name", String, default=""),
    Column("ally_id", String, default="0"),
    Column("villages", Integer, default=0),
    Column("points", Integer, default=0),
    Column("rank", Integer, default=0),
    Column("last_seen", DateTime(timezone=True), default=func.now())
)

villages_table = Table("villages", metadata,
    Column("id", String, primary_key=True),
    Column("name", String, default=""),
    Column("x", Integer, default=0),
    Column("y", Integer, default=0),
    Column("points", Integer, default=0),
    Column("wood_prod", Float, default=0),
    Column("stone_prod", Float, default=0),
    Column("iron_prod", Float, default=0),
    Column("last_seen", DateTime(timezone=True), default=func.now()),
    Column("is_owned", Boolean, default=False),
    Column("owner_id", String, default="0")
)

allies_table = Table("allies", metadata,
    Column("id", String, primary_key=True),
    Column("name", String, default=""),
    Column("tag", String, default=""),
    Column("members", Integer, default=0),
    Column("villages", Integer, default=0),
    Column("points", Integer, default=0),
    Column("all_points", Integer, default=0),
    Column("rank", Integer, default=0),
    Column("last_seen", DateTime(timezone=True), default=func.now())
)


async def download_file(url):
    logger.info(f"Pobieranie danych z url: {url}")
    target_url = url
    async with httpx.AsyncClient(follow_redirects=True) as client:
        response = await client.get(target_url)
        logger.info(f"HTTP Request: GET {target_url} \"HTTP/{response.http_version} {response.status_code} {response.reason_phrase}\"")
        if response.status_code == 200:
            return response.content
        else:
            raise Exception(f"Failed to download {url}. Status: {response.status_code}")


async def upsert_data(table, df, chunk_size=500):
    if df.empty:
        return

    # Oczyszczanie stringów z + i URL encodowania (częste w danych Plemion)
    for col in df.select_dtypes(include=['object']):
        df[col] = df[col].apply(lambda x: urllib.parse.unquote_plus(str(x)) if pd.notnull(x) else "")
        
    df['last_seen'] = pd.Timestamp.now(tz='UTC')
    
    logger.info(f"Upsertowanie łącznie {len(df)} rekordów do tabeli {table.name}...")

    async with engine.begin() as conn:
        for i in range(0, len(df), chunk_size):
            chunk = df.iloc[i:i+chunk_size]
            records = chunk.to_dict(orient="records")

            # Podstawa dla INSERT
            stmt = insert(table).values(records)

            # Znajdź kolumny na które jest założony primary/unique
            index_elements = [c.name for c in table.primary_key.columns]

            if index_elements:
                # Kolumny, ktore zostaną zaktualizowane w ON CONFLICT
                update_dict = {
                    c.name: c for c in stmt.excluded if c.name not in index_elements
                }
                update_dict["last_seen"] = func.now()
                
                # Wklejanie za pomoca INSERT ... ON CONFLICT DO UPDATE
                on_conflict_stmt = stmt.on_conflict_do_update(
                    index_elements=index_elements,
                    set_=update_dict
                )
                await conn.execute(on_conflict_stmt)
            else:
                # Jeżeli brak primary key (nie występuje tu)
                await conn.execute(stmt)

async def sync_world_data():
    try:
        # Tworzenie brakujących tabel (ale TWB raczej i tak je stworzy)
        async with engine.begin() as conn:
            await conn.run_sync(metadata.create_all)
            
        # 1. Plemiona (Allys)
        # format: $id, $name, $tag, $members, $villages, $points, $all_points, $rank
        ally_url = f"{endpoint}/map/ally.txt"
        content = await download_file(ally_url)
        df_ally = pd.read_csv(
            BytesIO(content),
            delimiter=',',
            names=["id", "name", "tag", "members", "villages", "points", "all_points", "rank"],
            dtype={"id": str, "name": str, "tag": str},
            encoding='utf-8'
        )
        await upsert_data(allies_table, df_ally)

        # 2. Gracze (Players)
        # format: $id, $name, $ally, $villages, $points, $rank
        player_url = f"{endpoint}/map/player.txt"
        content = await download_file(player_url)
        df_player = pd.read_csv(
            BytesIO(content),
            delimiter=',',
            names=["id", "name", "ally_id", "villages", "points", "rank"],
            dtype={"id": str, "name": str, "ally_id": str},
            encoding='utf-8'
        )
        await upsert_data(players_table, df_player)

        # 3. Wioski (Villages)
        # format: $id, $name, $x, $y, $player, $points, $rank
        # TWB oczekuje: id, name, x, y, owner_id, points 
        # wood_prod / stone_prod / iron_prod / is_owned i tak są ustawiane by TWB gdzies, default to 0 i False.
        village_url = f"{endpoint}/map/village.txt"
        content = await download_file(village_url)
        df_village = pd.read_csv(
            BytesIO(content),
            delimiter=',',
            names=["id", "name", "x", "y", "owner_id", "points", "rank_village"],
            dtype={"id": str, "name": str, "owner_id": str},
            encoding='utf-8'
        )
        # Odrzucamy kolumne rank_village bo nie ma jej w modelach TWB!
        df_village = df_village.drop(columns=["rank_village"])
        await upsert_data(villages_table, df_village)

        logger.info("Zakończono synchronizację ze światem.")
    except Exception as e:
        logger.error(f"Błąd podczas synchronizacji ze wiatem: {e}")

if __name__ == "__main__":
    asyncio.run(sync_world_data())
