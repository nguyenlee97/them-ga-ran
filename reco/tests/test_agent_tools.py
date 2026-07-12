import os
import sys
import unittest


sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

from app.agent.tools import _compact_product


class AgentProductCompactionTests(unittest.TestCase):
    def test_get_item_details_expose_real_combo_contents(self):
        product = {
            "_id": "p1",
            "sku": "d-bucket4-ff",
            "name_vi": "Combo Nhóm 2 No Nê",
            "price": 169000,
            "category": "Combo Nhóm",
            "isCombo": True,
            "description": "4 Miếng gà + 1 Khoai tây chiên (vừa) + 2 Ly Pepsi",
            "comboItems": [
                {"qty": 4, "note": "Miếng gà"},
                {"qty": 1, "note": "Khoai tây chiên (vừa)"},
                {"qty": 2, "note": "Ly Pepsi"},
            ],
        }
        compact = _compact_product(product, details=True)
        self.assertEqual(compact["description"], product["description"])
        self.assertEqual(compact["comboContents"][0], {
            "sku": None, "qty": 4, "item": "Miếng gà",
        })

    def test_search_compaction_does_not_expand_descriptions(self):
        compact = _compact_product({
            "_id": "p1", "name_vi": "Combo", "description": "long", "isCombo": True,
        })
        self.assertNotIn("description", compact)
        self.assertNotIn("comboContents", compact)


if __name__ == "__main__":
    unittest.main()
