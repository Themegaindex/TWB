import unittest
import time
import logging
from unittest.mock import MagicMock, patch
from game.attack import AttackManager
from game.reports import ReportManager

class TestFarmingOptimization(unittest.TestCase):
    def setUp(self):
        # Minimal configuration matching config.example.json structure
        self.config = {
            "bot": {"debug": False},
            "farms": {
                "farm": True,
                "search_radius": 50,
                "max_farms": 15,
                "smart_farming": True,
                "min_farm_capacity": 100,
                "min_farm_units": 5
            }
        }
        
        # Mocking components for AttackManager
        self.wrapper = MagicMock()
        self.wrapper.last_h = "test_h"
        self.wrapper.reporter = MagicMock()
        
        self.troopmanager = MagicMock()
        self.troopmanager.troops = {"spear": "100", "sword": "100"}
        self.troopmanager.can_attack = True
        self.troopmanager.carry_capacity = {"spear": 25, "sword": 15}
        self.troopmanager.can_scout = True
        
        self.map = MagicMock()
        self.map.villages = {
            "500": {"id": "500", "location": [500, 500], "owner": "0", "points": 10},
            "501": {"id": "501", "location": [501, 501], "owner": "0", "points": 15}
        }
        self.map.get_dist = MagicMock(return_value=10.0)
        
        # Initialize AttackManager and its logger
        self.attack_manager = AttackManager(
            wrapper=self.wrapper, 
            village_id="100", 
            troopmanager=self.troopmanager, 
            map=self.map
        )
        self.attack_manager.logger = logging.getLogger("AttacksTest")
        
        # Setup targets
        self.attack_manager.targets = [
            [{"id": "500", "location": [500, 500]}, 1.0],
            [{"id": "501", "location": [501, 501]}, 2.0]
        ]
        self.attack_manager.template = {"spear": 5}
        self.attack_manager.max_farms = 10

    @patch("game.attack.AttackCache")
    @patch("game.attack.DatabaseManager")
    def test_tc1_early_exit_on_no_units(self, mock_db, mock_cache):
        """TC-1: Gdy enough_in_village() zwraca 'Missing spear', pętla kończy się po pierwszej iteracji"""
        mock_cache.cache_grab.return_value = {}
        mock_cache.get_cache.return_value = {}
        mock_db.reserve_farm_loot.return_value = (True, 100, 100, 100)
        self.attack_manager.enough_in_village = MagicMock(return_value="Missing spear")
        
        with patch.object(self.attack_manager, 'send_farm', wraps=self.attack_manager.send_farm) as spy_send_farm:
            result = self.attack_manager.run()
            self.assertTrue(result)
            self.assertEqual(spy_send_farm.call_count, 1)

    @patch("game.attack.AttackCache")
    @patch("game.attack.DatabaseManager")
    def test_tc2_single_read_cache(self, mock_db, mock_cache):
        """TC-2: AttackCache.cache_grab wywołany dokładnie RAZ przez cały run()"""
        mock_cache.cache_grab.return_value = {}
        mock_cache.get_cache.return_value = {}
        mock_db.reserve_farm_loot.return_value = (True, 100, 100, 100)
        self.attack_manager.enough_in_village = MagicMock(return_value=False)
        
        with patch.object(self.attack_manager, 'can_attack', return_value=False):
            self.attack_manager.run()
        self.assertEqual(mock_cache.cache_grab.call_count, 1)

    @patch("game.attack.AttackCache")
    @patch("game.attack.DatabaseManager")
    def test_tc3_deduplication_same_target(self, mock_db, mock_cache):
        """TC-3: Lista celów z dwoma identycznymi village_id → tylko jeden atak wysłany"""
        target_v = {"id": "500", "location": [500, 500]}
        mock_cache.cache_grab.return_value = {}
        mock_cache.get_cache.return_value = {}
        mock_db.reserve_farm_loot.return_value = (True, 100, 100, 100)
        
        with patch.object(self.attack_manager, 'get_targets'):
            self.attack_manager.targets = [[target_v, 1.0], [target_v, 2.0]]
            with patch.object(self.attack_manager, 'send_farm', return_value=1) as mock_send:
                self.attack_manager.run()
                self.assertEqual(mock_send.call_count, 1)

    @patch("game.attack.AttackCache")
    @patch("game.attack.DatabaseManager")
    def test_tc4_ttl_triggers_scout(self, mock_db, mock_cache):
        """TC-4: Raport starszy niż 12h → bot wysyła skaut zamiast ataku"""
        target_id = "500"
        old_ts = time.time() - (13 * 3600)
        mock_cache.get_cache.return_value = {"last_attack": old_ts, "safe": True, "scout": True}
        self.attack_manager.scout = MagicMock(return_value=True)
        self.attack_manager.attack = MagicMock()
        self.attack_manager.repman = MagicMock()
        self.attack_manager.repman.safe_to_engage.return_value = 1
        
        result = self.attack_manager.can_attack(target_id)
        self.assertFalse(result)
        self.attack_manager.scout.assert_called_once_with(target_id)

    @patch("game.reports.DatabaseManager")
    @patch("game.reports.AttackCache")
    def test_tc5_reports_guard_clause_none(self, mock_cache, mock_db):
        """TC-5: reports.py nie rzuca AttributeError gdy fragment HTML jest None"""
        rep_man = ReportManager(wrapper=self.wrapper, village_id="100")
        rep_man.logger = logging.getLogger("ReportsTest")
        bad_html = "<html><body>No data here</body></html>"
        try:
            rep_man.attack_report(bad_html, "999")
            success = True
        except Exception as e:
            success = False
            self.fail(f"ReportManager.attack_report raised an exception: {e}")
        self.assertTrue(success)

if __name__ == '__main__':
    unittest.main()
