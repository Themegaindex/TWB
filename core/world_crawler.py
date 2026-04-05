import logging
import requests
import urllib.parse
from datetime import datetime
from core.database import DatabaseManager, DBVillage, DBPlayer, DBAlly, get_engine
from core.filemanager import FileManager
from sqlalchemy import insert, delete

logger = logging.getLogger("WorldCrawler")

class WorldCrawler:
    """
    Downloads and parses public world data files from Tribal Wars servers:
    village.txt, player.txt, ally.txt, conquer.txt, kill_*.txt
    """

    @staticmethod
    def get_server_url():
        config = FileManager.load_json_file("config.json")
        if not config or 'server' not in config:
            return None
        endpoint = config['server'].get('endpoint', '')
        if not endpoint:
            return None
        # Extract base world URL, e.g. https://pl227.plemiona.pl/
        parsed = urllib.parse.urlparse(endpoint)
        return f"{parsed.scheme}://{parsed.netloc}"

    @staticmethod
    def download_file(url_base, filename):
        url = f"{url_base}/map/{filename}"
        logger.info(f"Downloading {url}...")
        try:
            res = requests.get(url, timeout=30)
            if res.status_code == 200:
                return res.text
        except Exception as e:
            logger.error(f"Failed to download {url}: {e}")
        return None

    @staticmethod
    def parse_txt(content):
        """CSV-like format with URL encoded strings"""
        if not content:
            return []
        lines = content.strip().split('\n')
        rows = []
        for line in lines:
            parts = line.split(',')
            # URL decode parts
            decoded = [urllib.parse.unquote_plus(p) for p in parts]
            rows.append(decoded)
        return rows

    @staticmethod
    def update_villages(rows):
        """
        village.txt: $id, $name, $x, $y, $player_id, $points, $rank
        """
        if not rows: return
        s = DatabaseManager._session()
        engine = get_engine()
        is_pg = engine.dialect.name == 'postgresql'
        
        logger.info(f"Upserting {len(rows)} villages...")
        
        try:
            # Batch items
            batch_size = 500
            for i in range(0, len(rows), batch_size):
                batch = rows[i:i + batch_size]
                values = []
                for r in batch:
                    if len(r) < 6: continue
                    values.append({
                        'id': r[0],
                        'name': r[1],
                        'x': int(r[2]),
                        'y': int(r[3]),
                        'owner_id': r[4],
                        'points': int(r[5]),
                        'last_seen': datetime.utcnow()
                    })
                
                if is_pg:
                    from sqlalchemy.dialects.postgresql import insert as pg_insert
                    stmt = pg_insert(DBVillage).values(values)
                    stmt = stmt.on_conflict_do_update(
                        index_elements=['id'],
                        set_={
                            'name': stmt.excluded.name,
                            'points': stmt.excluded.points,
                            'owner_id': stmt.excluded.owner_id,
                            'last_seen': stmt.excluded.last_seen
                        }
                    )
                    s.execute(stmt)
                else:
                    for val in values:
                        v = s.get(DBVillage, val['id'])
                        if not v:
                            v = DBVillage(id=val['id'])
                            s.add(v)
                        v.name = val['name']
                        v.points = val['points']
                        v.owner_id = val['owner_id']
                        v.last_seen = val['last_seen']
            s.commit()
            logger.info("Villages updated successfully.")
        except Exception as e:
            logger.error(f"Error updating villages: {e}")
            s.rollback()
        finally:
            s.close()

    @staticmethod
    def update_players(rows):
        """
        player.txt: $id, $name, $ally_id, $villages, $points, $rank
        """
        if not rows: return
        s = DatabaseManager._session()
        engine = get_engine()
        is_pg = engine.dialect.name == 'postgresql'
        
        logger.info(f"Upserting {len(rows)} players...")
        
        try:
            batch_size = 500
            for i in range(0, len(rows), batch_size):
                batch = rows[i:i + batch_size]
                values = []
                for r in batch:
                    if len(r) < 6: continue
                    values.append({
                        'id': r[0],
                        'name': r[1],
                        'ally_id': r[2],
                        'villages': int(r[3]),
                        'points': int(r[4]),
                        'rank': int(r[5]),
                        'last_seen': datetime.utcnow()
                    })
                
                if is_pg:
                    from sqlalchemy.dialects.postgresql import insert as pg_insert
                    stmt = pg_insert(DBPlayer).values(values)
                    stmt = stmt.on_conflict_do_update(
                        index_elements=['id'],
                        set_={
                            'name': stmt.excluded.name,
                            'ally_id': stmt.excluded.ally_id,
                            'villages': stmt.excluded.villages,
                            'points': stmt.excluded.points,
                            'rank': stmt.excluded.rank,
                            'last_seen': stmt.excluded.last_seen
                        }
                    )
                    s.execute(stmt)
                else:
                    for val in values:
                        v = s.get(DBPlayer, val['id'])
                        if not v:
                            v = DBPlayer(id=val['id'])
                            s.add(v)
                        v.name = val['name']
                        v.ally_id = val['ally_id']
                        v.villages = val['villages']
                        v.points = val['points']
                        v.rank = val['rank']
                        v.last_seen = val['last_seen']
            s.commit()
            logger.info("Players updated successfully.")
        except Exception as e:
            logger.error(f"Error updating players: {e}")
            s.rollback()
        finally:
            s.close()

    @staticmethod
    def update_allies(rows):
        """
        ally.txt: $id, $name, $tag, $members, $villages, $points, $all_points, $rank
        """
        if not rows: return
        s = DatabaseManager._session()
        engine = get_engine()
        is_pg = engine.dialect.name == 'postgresql'
        
        logger.info(f"Upserting {len(rows)} allies...")
        
        try:
            batch_size = 500
            for i in range(0, len(rows), batch_size):
                batch = rows[i:i + batch_size]
                values = []
                for r in batch:
                    if len(r) < 8: continue
                    values.append({
                        'id': r[0],
                        'name': r[1],
                        'tag': r[2],
                        'members': int(r[3]),
                        'villages': int(r[4]),
                        'points': int(r[5]),
                        'all_points': int(r[6]),
                        'rank': int(r[7]),
                        'last_seen': datetime.utcnow()
                    })
                
                if is_pg:
                    from sqlalchemy.dialects.postgresql import insert as pg_insert
                    stmt = pg_insert(DBAlly).values(values)
                    stmt = stmt.on_conflict_do_update(
                        index_elements=['id'],
                        set_={
                            'name': stmt.excluded.name,
                            'tag': stmt.excluded.tag,
                            'members': stmt.excluded.members,
                            'villages': stmt.excluded.villages,
                            'points': stmt.excluded.points,
                            'all_points': stmt.excluded.all_points,
                            'rank': stmt.excluded.rank,
                            'last_seen': stmt.excluded.last_seen
                        }
                    )
                    s.execute(stmt)
                else:
                    for val in values:
                        v = s.get(DBAlly, val['id'])
                        if not v:
                            v = DBAlly(id=val['id'])
                            s.add(v)
                        v.name = val['name']
                        v.tag = val['tag']
                        v.members = val['members']
                        v.villages = val['villages']
                        v.points = val['points']
                        v.all_points = val['all_points']
                        v.rank = val['rank']
                        v.last_seen = val['last_seen']
            s.commit()
            logger.info("Allies updated successfully.")
        except Exception as e:
            logger.error(f"Error updating allies: {e}")
            s.rollback()
        finally:
            s.close()

    @staticmethod
    def update_conquers(rows):
        """
        conquer.txt: $village_id, $timestamp, $new_owner, $old_owner
        """
        if not rows: return
        logger.info(f"Syncing {len(rows)} conquer events...")
        conquer_data = []
        for r in rows:
            if len(r) < 4: continue
            try:
                conquer_data.append({
                    "village_id": r[0],
                    "timestamp": datetime.fromtimestamp(int(r[1])),
                    "new_owner": r[2],
                    "old_owner": r[3]
                })
            except Exception: continue
        
        if conquer_data:
            inserted = DatabaseManager.bulk_upsert_conquers(conquer_data)
            logger.info(f"Conquers updated: {inserted} new records.")

    @staticmethod
    def update_kill_scores(kind, rows):
        """
        kill_*.txt: $rank, $player_id, $score
        """
        if not rows: return
        logger.info(f"Syncing {len(rows)} kill scores ({kind})...")
        
        field_score = f"score_{kind}"
        field_rank = f"rank_{kind}"
        
        for r in rows:
            if len(r) < 3: continue
            try:
                score_data = {
                    field_rank: int(r[0]),
                    field_score: int(r[2])
                }
                DatabaseManager.upsert_kill_scores(r[1], **score_data)
            except Exception: continue
        logger.info(f"Kill scores ({kind}) updated successfully.")

    @staticmethod
    def full_crawl():
        url_base = WorldCrawler.get_server_url()
        if not url_base:
            logger.error("Could not determine server URL for world data.")
            return

        logger.info(f"Starting world crawl for {url_base}...")
        
        # 1. Allies
        content = WorldCrawler.download_file(url_base, "ally.txt")
        if content:
            WorldCrawler.update_allies(WorldCrawler.parse_txt(content))
            
        # 2. Players
        content = WorldCrawler.download_file(url_base, "player.txt")
        if content:
            WorldCrawler.update_players(WorldCrawler.parse_txt(content))
            
        # 3. Villages
        content = WorldCrawler.download_file(url_base, "village.txt")
        if content:
            WorldCrawler.update_villages(WorldCrawler.parse_txt(content))
            
        # 4. Conquers
        content = WorldCrawler.download_file(url_base, "conquer.txt")
        if content:
            WorldCrawler.update_conquers(WorldCrawler.parse_txt(content))
            
        # 5. Kill Scores
        for kind in ["att", "def", "all"]:
            content = WorldCrawler.download_file(url_base, f"kill_{kind}.txt")
            if content:
                WorldCrawler.update_kill_scores(kind, WorldCrawler.parse_txt(content))
            
        logger.info("Full world crawl completed.")

# CLI entry point
if __name__ == "__main__":
    WorldCrawler.full_crawl()
