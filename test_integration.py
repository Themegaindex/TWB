import unittest
import os
import json
from unittest.mock import MagicMock
from core.database import get_engine, Base, DatabaseManager, get_session, DBVillage, DBAttack
from game.reports import ReportManager
# set in memory DB
import core.database as db_mod
db_mod.DB_PATH = ":memory:"
db_mod._engine = None
db_mod._SessionLocal = None

class TestIntegration(unittest.TestCase):
    def setUp(self):
        # ensure clean db
        db_mod._engine = None
        db_mod._SessionLocal = None
        self.engine = get_engine()
        Base.metadata.create_all(self.engine)
        
    def tearDown(self):
        Base.metadata.drop_all(self.engine)

    def test_report_manager_to_db(self):
        wrapper = MagicMock()
        rm = ReportManager(wrapper=wrapper, village_id="123")
        rm.game_state = {"player": {"id": "111"}}
        
        # simulated attack HTML
        report_html = """
        <span class="small grey">10.10.25 12:00:00</span>
        image_attack_won
        <table id="attack_info_att" data-id="123" data-player="111">
           Agresor:
           <table id="attack_info_att_units">
               <tr><td></td></tr>
               <tr><td>100</td><td>50</td></tr>
               <tr><td>10</td><td>5</td></tr>
           </table>
        </table>
        
        <table id="attack_info_def" data-id="456" data-player="222">
           Obrońca:
           <table id="attack_info_def_units">
               <tr><td></td></tr>
               <tr><td>200</td><td>100</td></tr>
               <tr><td>200</td><td>100</td></tr>
           </table>
        </table>
        
        <table id="attack_results">
           <span class="icon header wood"></span>1000
           <span class="icon header stone"></span>500
           <span class="icon header iron"></span>200
        </table>
        """
        
        rm.logger = MagicMock()
        
        self.assertTrue(rm.attack_report(report_html, "test_report_1"))
        
        # Check if saved to DB
        attacks = DatabaseManager.get_attack_history("456")
        self.assertEqual(len(attacks), 1)
        self.assertEqual(attacks[0]["origin_id"], "123")
        self.assertEqual(attacks[0]["target_id"], "456")
        self.assertEqual(attacks[0]["loot_wood"], 1000)
        self.assertEqual(attacks[0]["loot_stone"], 500)
        self.assertEqual(attacks[0]["loot_iron"], 200)
        print("Integration DB+Report tests PASSED!")

if __name__ == "__main__":
    unittest.main()
