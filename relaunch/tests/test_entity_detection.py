"""
Entity detection regression tests.

Run this file before shipping any change to entity_detection.py or scrub_batch.py:
  python -m unittest relaunch.tests.test_entity_detection
"""

from __future__ import annotations

import unittest

from relaunch.scrub.entity_detection import is_true_entity


class EntityDetectionTests(unittest.TestCase):
    def test_maralyn_cantor_trust_adjacent_not_entity(self):
        row = {
            "public.owner1FirstName": "Maralyn",
            "public.owner1LastName": "Cantor",
            "public.owner2FirstName": "",
            "public.owner2LastName": "The Maralyn Cantor Living Trust",
            "public.companyName": "",
            "public.owner2Company": "The Maralyn Cantor Living Trust",
        }
        self.assertFalse(is_true_entity(row))

    def test_maria_gerontides_trust_adjacent_not_entity(self):
        row = {
            "public.owner1FirstName": "Maria",
            "public.owner1LastName": "Gerontides",
            "public.owner2FirstName": "",
            "public.owner2LastName": "The Maria Gerontides Trust",
            "public.companyName": "",
            "public.owner2Company": "The Maria Gerontides Trust",
        }
        self.assertFalse(is_true_entity(row))

    def test_cccsd_sunnybrook_is_true_entity(self):
        row = {
            "listing.address.unparsedAddress": "1489 Sunnybrook Rd.",
            "public.owner1FirstName": "",
            "public.owner1LastName": "Central Contra Costa Sanitary District",
            "public.owner2FirstName": "",
            "public.owner2LastName": "",
            "public.companyName": "",
        }
        self.assertTrue(is_true_entity(row))

    def test_primevista_holdings_is_true_entity(self):
        row = {
            "public.owner1FirstName": "",
            "public.owner1LastName": "Primevista I Holdings Inc",
            "public.owner2FirstName": "",
            "public.owner2LastName": "",
            "public.companyName": "Primevista I Holdings Inc, ",
        }
        self.assertTrue(is_true_entity(row))

    def test_blank_names_no_keyword_is_ambiguous(self):
        row = {
            "public.owner1FirstName": "",
            "public.owner1LastName": "Smith",
            "public.owner2FirstName": "",
            "public.owner2LastName": "",
            "public.companyName": "",
        }
        self.assertIsNone(is_true_entity(row))

    def test_owner2_first_name_blocks_entity_even_with_trust_language(self):
        row = {
            "public.owner1FirstName": "",
            "public.owner1LastName": "Smith Family Trust",
            "public.owner2FirstName": "Jane",
            "public.owner2LastName": "Smith",
            "public.companyName": "Smith Family Trust",
        }
        self.assertFalse(is_true_entity(row))


if __name__ == "__main__":
    unittest.main()
