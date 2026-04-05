import unittest
from unittest.mock import MagicMock, patch
from bs4 import BeautifulSoup
import time
import os
from game.scavenging import ScavengingManager, ScavengeLevel, ScavengeAssignment

class TestScavengingManager(unittest.TestCase):
    def setUp(self):
        self.village_id = 123
        self.config = {
            "gather_enabled": True,
            "gather_levels": [1, 2, 3],
            "gather_unit_priority": ["sword", "spear", "axe"],
            "gather_min_fill_ratio": 0.85,
            "gather_reserve_for_farm": {
                "light": 1.0,
                "marcher": 1.0
            },
            "gather_cooldown_minutes": 5
        }
        self.wrapper = MagicMock()
        self.manager = ScavengingManager(self.village_id, self.config, self.wrapper)

    def test_calculate_optimal_split_basic(self):
        """500 mieczy + 300 pik → 3 poziomy, sprawdź że suma units ≤ input"""
        # Carry: spear=25, sword=15, axe=10
        # total_carry = 300*25 + 500*15 = 7500 + 7500 = 15000
        # Units total: 800
        # Avg carry: 15000 / 800 = 18.75
        
        units = {"spear": 300, "sword": 500}
        levels = [
            ScavengeLevel(1, capacity=1000, duration_seconds=0, is_locked=False, is_running=False),
            ScavengeLevel(2, capacity=2500, duration_seconds=0, is_locked=False, is_running=False),
            ScavengeLevel(3, capacity=5000, duration_seconds=0, is_locked=False, is_running=False),
        ]
        
        assignments = self.manager.calculate_optimal_split(units, levels)
        
        # Total units sent should not exceed input
        sent_spears = sum(a.units.get("spear", 0) for a in assignments)
        sent_swords = sum(a.units.get("sword", 0) for a in assignments)
        
        self.assertLessEqual(sent_spears, 300)
        self.assertLessEqual(sent_swords, 500)
        self.assertTrue(len(assignments) > 0)
        
        # Check if high capacity level is first
        self.assertEqual(assignments[0].level_id, 3)

    def test_calculate_optimal_split_not_enough_units(self):
        """za mało jednostek → pomiń poziom z niskim fill_ratio"""
        # Units: 10 spears (carry 250)
        # Level 1: capacity 1000. Min fill (0.85) = 850.
        # 250 < 850, so should skip.
        
        units = {"spear": 10}
        levels = [
            ScavengeLevel(1, capacity=1000, duration_seconds=0, is_locked=False, is_running=False)
        ]
        
        assignments = self.manager.calculate_optimal_split(units, levels)
        self.assertEqual(len(assignments), 0)

    def test_calculate_optimal_split_single_level(self):
        """tylko 1 wolny poziom → wszystko do niego (jeśli fill_ratio ok)"""
        # Units: 100 spears (carry 2500)
        # Level 1: capacity 1000.
        # Should take units needed for 1000 carry.
        # avg_carry = 25. units_needed = 1000/25 = 40.
        
        units = {"spear": 100}
        levels = [
            ScavengeLevel(1, capacity=1000, duration_seconds=0, is_locked=False, is_running=False)
        ]
        
        assignments = self.manager.calculate_optimal_split(units, levels)
        self.assertEqual(len(assignments), 1)
        self.assertEqual(assignments[0].level_id, 1)
        self.assertEqual(assignments[0].units["spear"], 40)

    def test_parse_available_units_excludes_reserved(self):
        """LK w HTML → nie powinna trafić do wyniku"""
        fixture_path = os.path.join("tests", "fixtures", "scavenge_page.html")
        with open(fixture_path, "r", encoding="utf-8") as f:
            html = f.read()
        
        soup = BeautifulSoup(html, "html.parser")
        units = self.manager.parse_available_units(soup)
        
        # Fixture has light=100, spear=1000, sword=500, axe=200
        # Config has light reserved 100%
        self.assertNotIn("light", units)
        self.assertEqual(units.get("spear"), 1000)
        self.assertEqual(units.get("sword"), 500)
        self.assertEqual(units.get("axe"), 200)

    def test_cooldown_respected(self):
        """run() wywołane dwa razy szybko → drugi call nie wysyła requestów"""
        with patch.object(self.manager, 'fetch_scavenge_page') as mock_fetch:
            mock_fetch.return_value = BeautifulSoup("<html></html>", "html.parser")
            
            # First run
            self.manager.run()
            self.assertTrue(mock_fetch.called)
            
            mock_fetch.reset_mock()
            
            # Second run (immediately)
            self.manager.run()
            self.assertFalse(mock_fetch.called)

    def test_parse_scavenge_levels_from_fixture(self):
        """Test parsing levels from real fixture"""
        fixture_path = os.path.join("tests", "fixtures", "scavenge_page.html")
        with open(fixture_path, "r", encoding="utf-8") as f:
            html = f.read()
        
        soup = BeautifulSoup(html, "html.parser")
        levels = self.manager.parse_scavenge_levels(soup)
        
        # Fixture has levels 1, 2, 3 free and 4 locked.
        # gather_levels config is [1, 2, 3]
        self.assertEqual(len(levels), 3)
        self.assertEqual(levels[0].level_id, 1)
        self.assertEqual(levels[0].capacity, 1000)
        self.assertEqual(levels[1].level_id, 2)
        self.assertEqual(levels[1].capacity, 2500)
        self.assertEqual(levels[2].level_id, 3)
        self.assertEqual(levels[2].capacity, 5000)

if __name__ == '__main__':
    unittest.main()
