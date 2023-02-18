#!/usr/bin/env python3

import requests
import unittest

import pylomena


class TestSites(unittest.TestCase):
    def test_sites(self) -> None:
        for name, url in pylomena.KNOWN_SITES.items():
            site = pylomena.Site(url)
            
            imgs = site.search_images("*")
            self.assertGreater(imgs.total, 1000, msg=f"query images from {name}")
            self.assertIsInstance(next(imgs), pylomena.Image, msg=f"query images from {name}")
            
            tags = site.search_tags("*")
            self.assertGreater(tags.total, 10, msg=f"query tags from {name}")
            self.assertIsInstance(next(tags), pylomena.Tag, msg=f"query tags from {name}")
            
            # not every site implements this API
            try:
                filters = site.search_filters("*")
            except requests.exceptions.HTTPError as e:
                if e.response.status_code != 404:
                    raise e
            else:
                self.assertGreaterEqual(imgs.total, 1, msg=f"query filters from {name}")
                self.assertIsInstance(next(filters), pylomena.Filter, msg=f"query filters from {name}")


if __name__ == '__main__':
    unittest.main()

