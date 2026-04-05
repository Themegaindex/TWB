import logging
from sqlalchemy import text
from core.database import get_session

logger = logging.getLogger("DbDataProvider")

class DbDataProvider:
    @staticmethod
    def get_target_tribe(target_id):
        """
        Zwraca informacje o plemieniu gracza (z tabeli allies) dla danego ID wioski (target_id).
        Pozwala całkowicie wyeliminować żądania do 'game.php?screen=info_player'.
        """
        session = get_session()
        if not session:
            return None
            
        try:
            # target_id jako int poniewaz nasza tabela bazodanowa uzywa INTEGER id
            target_id_int = int(target_id)
            query = text("""
                SELECT a.name, a.tag, a.id as ally_id
                FROM villages v
                JOIN players p ON v.player_id = p.id
                JOIN allies a ON p.ally_id = a.id
                WHERE v.id = :village_id
            """)
            result = session.execute(query, {"village_id": target_id_int}).fetchone()
            if result:
                # W zaleznosci od sterownika zwroci tuplę po kolumnach
                return {
                    "name": result[0],
                    "tag": result[1],
                    "id": result[2]
                }
            return None
        except ValueError:
            return None
        except Exception as e:
            logger.error(f"Błąd podczas pobierania informacji o plemieniu: {e}")
            return None
        finally:
            session.close()

    @staticmethod
    def find_barbarians(bot_x, bot_y, max_distance=15, min_points=100):
        """
        Wyszukuje wioski barbarzyńskie wokół podanych współrzędnych.
        Korzystamy z matematycznego wzoru na odległość euklidesową
        całkowicie eliminując skanowanie mapy poprzez zapytania HTTP.
        """
        session = get_session()
        if not session:
            return []
        
        try:
            # SQRT(POWER...) użyte jako matematyczny filtr na odległość.
            # Dzięki indeksom i warunkowi `player_id = 0 AND points > :min_points`
            # wyszukiwanie będzie ultraszybkie.
            query = text("""
                SELECT id, name, x, y, points,
                       SQRT(POWER(x - :bot_x, 2) + POWER(y - :bot_y, 2)) AS distance
                FROM villages
                WHERE player_id = 0
                  AND points > :min_points
                  AND SQRT(POWER(x - :bot_x, 2) + POWER(y - :bot_y, 2)) <= :max_distance
                ORDER BY distance ASC
            """)
            
            params = {
                "bot_x": bot_x,
                "bot_y": bot_y,
                "max_distance": max_distance,
                "min_points": min_points
            }
            
            result = session.execute(query, params).fetchall()
            
            farms = []
            for row in result:
                # Format wyjściowy jest dostosowany do starych metod TWB ("location", "id" to string)
                farms.append({
                    "id": str(row[0]),
                    "name": row[1],
                    "location": [row[2], row[3]],
                    "points": row[4],
                    "distance": float(row[5]),
                    "owner": "0",
                    "tribe": None,
                    "safe": False,
                    "scout": False,
                    "bonus": "0"
                })
                
            return farms
        except Exception as e:
            logger.error(f"Błąd podczas szukania farm w bazie danych: {e}")
            return []
        finally:
            session.close()
