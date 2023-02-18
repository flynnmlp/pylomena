#!/usr/bin/env python3

import unittest

import pylomena


class TestDerpibooru(unittest.TestCase):
    def setUp(self) -> None:
        self.derpibooru = pylomena.Site("https://derpibooru.org")
    
    def tearDown(self) -> None:
        pass
    
    def test_image(self) -> None:
        img = self.derpibooru.get_image(0)
        
        self.assertIn("derpy hooves", img.tags)
        self.assertNotIn("rainbow dash", img.tags)
        
        self.assertEqual(0, img.id)
    
    def test_tag(self) -> None:
        slug = self.derpibooru.tag_to_slug("oc:cream heart")
        
        self.assertEqual(slug, "oc-colon-cream+heart")
        
        tag = self.derpibooru.get_tag(slug)
        
        self.assertIn("oc-colon-button%27s+mom", tag.aliases)
        self.assertNotIn("rd", tag.aliases)
        
        self.assertEqual("oc", tag.category)
        self.assertEqual("oc:cream heart", tag.name)
        self.assertEqual("cream heart", tag.name_in_namespace)
        self.assertEqual(slug, tag.slug)
        
        self.assertIn("creamac", tag.implied_by_tags)
    
    # TODO: more test cases
    
    def test_tag_conversion(self) -> None:
        self.assertEqual(self.derpibooru.tag_to_slug("derpy hooves"), "derpy+hooves")
        self.assertEqual(self.derpibooru.tag_to_slug("oc:button mash"), "oc-colon-button+mash")
        
        self.assertEqual(self.derpibooru.tag_to_slug("mane five (g5)", False), "mane+five+(g5)")
        self.assertEqual(self.derpibooru.tag_to_slug("frog (hoof)", True), "frog+%28hoof%29")
        
        self.assertEqual(self.derpibooru.tag_to_slug("dj pon-3", True), "dj+pon-dash-3")
        self.assertEqual(self.derpibooru.tag_to_slug("test_test", True), "test_test")
    
    def test_valid_tags(self) -> None:
        self.derpibooru.validate_tag_slug("test")
        self.derpibooru.validate_tag_slug("test+test")
        self.derpibooru.validate_tag_slug("test-colon-test-dash-test-dot-test")
        self.derpibooru.validate_tag_slug("test%25test%27test%2b")
        
        with self.assertRaises(ValueError, msg="Invalid character"):
            self.derpibooru.validate_tag_slug(" ")
        with self.assertRaises(ValueError, msg="Invalid character"):
            self.derpibooru.validate_tag_slug("#")
        with self.assertRaises(ValueError, msg="Incomplete escape sequence"):
            self.derpibooru.validate_tag_slug("-")
        with self.assertRaises(ValueError, msg="Invalid escape sequence"):
            self.derpibooru.validate_tag_slug("-dash")
        with self.assertRaises(ValueError, msg="Incomplete escape sequence"):
            self.derpibooru.validate_tag_slug("%")
        with self.assertRaises(ValueError, msg="Invalid escape sequence"):
            self.derpibooru.validate_tag_slug("%gg")
        
        for i, tag in enumerate(self.derpibooru.search_tags("*", per_page=50)):
            if i >= 50:
                break
            
            slug = self.derpibooru.tag_to_slug(tag.name, True)
            if slug != tag.slug:
                slug = self.derpibooru.tag_to_slug(tag.name, False)
            self.assertEqual(tag.slug, slug)
            
            try:
                self.derpibooru.validate_tag_slug(tag.slug)
            except Exception:
                print(tag.slug)
                raise


if __name__ == '__main__':
    unittest.main()

