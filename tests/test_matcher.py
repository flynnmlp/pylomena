#!/usr/bin/env python3

import datetime
import unittest

from typing import Optional, Sequence

import pylomena

Interactions = Optional[Sequence[pylomena.Interaction]]


class TestMatcher(unittest.TestCase):
    def setUp(self) -> None:
        self.derpibooru = pylomena.Site(pylomena.KNOWN_SITES["derpibooru"])
        self.img = self.derpibooru.get_image(0)
    
    def match(self, query: str, interactions: Interactions = None) -> bool:
        return pylomena.parse_search(query).match(self.img, interactions)
    
    def assertMatch(self, query: str, interactions: Interactions = None) -> None:
        self.assertTrue(self.match(query, interactions))
    
    def assertNonMatch(self, query: str, interactions: Interactions = None) -> None:
        self.assertFalse(self.match(query, interactions))
    
    def test_tags(self) -> None:
        self.assertMatch("dErPy HoOvEs")
        self.assertNonMatch("rainbow dash")
        
        self.assertMatch("derpy hooves AND safe")
        self.assertMatch("derpy hooves && safe")
        self.assertMatch("derpy hooves,safe")
        self.assertMatch("derpy hooves OR rainbow dash")
        self.assertMatch("derpy hooves || rainbow dash")
        
        self.assertNonMatch("derpy hooves AND rainbow dash")
        self.assertNonMatch("twilight sparkle OR rainbow dash")
        
        self.assertNonMatch("!derpy hooves")
        self.assertNonMatch("-safe")
        self.assertMatch("NOT rainbow dash")
        
        self.assertMatch("derpy hooves AND (safe OR rainbow dash)")
        self.assertMatch("twilight sparkle OR (safe AND derpy hooves)")
        self.assertMatch("(safe OR rainbow dash) AND derpy hooves")
        self.assertMatch("(safe AND derpy hooves) OR twilight sparkle")
    
    def test_numbers(self) -> None:
        self.assertMatch("width:800")
        self.assertNonMatch("width:700")
        
        self.assertMatch("width.gt:700")
        self.assertMatch("width.lt:900")
        
        self.assertMatch("width.gte:700")
        self.assertMatch("width.lte:900")
        
        self.assertMatch("width.gte:800")
        self.assertMatch("width.lte:800")
        
        self.assertNonMatch("width.gt:800")
        self.assertNonMatch("width.lt:800")
        
        self.assertNonMatch("width.gte:900")
        self.assertNonMatch("width.lte:700")
        
        self.assertMatch("height:700")
        self.assertNonMatch("height:800")
        
        self.assertMatch("aspect_ratio.gt:1")
        self.assertNonMatch("aspect_ratio.lt:1")
        
        self.assertMatch("upvotes.gt:100")
        self.assertMatch("downvotes.gt:1")
        self.assertMatch("score.gt:1")
        self.assertMatch("faves.gt:1")
        self.assertMatch("tag_count.gt:1")
    
    def test_fuzzy(self) -> None:
        self.assertMatch("derpy hovet~2.0")
        self.assertNonMatch("derpy hovet~1.0")
        self.assertMatch("derppyy hovet~4.0")
        self.assertNonMatch("derppyy hovet~3.0")
    
    def test_dates_abs(self) -> None:
        self.assertMatch("created_at:2012")
        self.assertMatch("created_at:2012-01")
        self.assertMatch("created_at:2012-01-02")
        
        self.assertMatch("created_at.gt:2012-01-01")
        self.assertMatch("created_at.gt:2011-12")
        self.assertMatch("created_at.gt:2011")
        
        self.assertMatch("created_at.lt:2012-01-03")
        self.assertMatch("created_at.lt:2012-02")
        self.assertMatch("created_at.lt:2013")
    
    def test_dates_rel(self) -> None:
        now = datetime.datetime.now().astimezone(tz=datetime.timezone.utc)
        date = now - datetime.timedelta(hours=1, minutes=30)
        datestr = date.strftime("%Y-%m-%dT%H:%M:%MZ")
        
        origdate = self.img.created_at
        try:
            self.img.created_at = datestr
            
            self.assertMatch("created_at.gt:2 hours ago")
            self.assertMatch("created_at.gt:1 day ago")
            self.assertMatch("created_at.gt:1 month ago")
            self.assertMatch("created_at.gt:1 year ago")
            
            self.assertMatch("created_at.lt:1 second ago")
            self.assertMatch("created_at.lt:1 minute ago")
            self.assertMatch("created_at.lt:1 hour ago")
            
            self.assertNonMatch("created_at.gt:1 hour ago")
            self.assertNonMatch("created_at.gt:1 minute ago")
            self.assertNonMatch("created_at.gt:1 second ago")
            
            self.assertNonMatch("created_at.lt:2 hours ago")
            self.assertNonMatch("created_at.lt:1 day ago")
            self.assertNonMatch("created_at.lt:1 month ago")
            self.assertNonMatch("created_at.lt:1 year ago")
        finally:
            self.img.created_at = origdate
    
    def test_interactions(self) -> None:
        data: Sequence[pylomena.JSONObject] = [
            {
                "image_id": 0,
                "interaction_type": "faved",
                "user_id": 0,
                "value": ""
            },
            {
                "image_id": 0,
                "interaction_type": "voted",
                "user_id": 0,
                "value": "up"
            }
        ]
        
        interactions: Interactions = [pylomena.Interaction(i) for i in data]
        
        self.assertMatch("my:faves", interactions)
        self.assertNonMatch("my:faves", [])
        self.assertMatch("my:upvotes", interactions)
        self.assertNonMatch("my:upvotes", [])
        
        self.assertNonMatch("my:downvotes", interactions)


if __name__ == '__main__':
    unittest.main()

