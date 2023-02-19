import requests
import urllib
import string
import time

from typing import cast, Any, Callable, Dict, Generic, Iterator, List, Optional, TypeVar

from .types import Filter, Image, Tag, JSONData

__all__ = ["Site"]

T = TypeVar("T")


class Site:
    def __init__(self, base_url: str):
        self.base_url = base_url
        self.api_base = urllib.parse.urljoin(self.base_url, "/api/v1/json/")
    
    def api_call(self, method: str, *args: Any, **kwargs: Any) -> requests.Response:
        """
        perform a GET API call to the endpoint `method`.
        all other arguments are passed down to requests.get()
        """
        
        url = urllib.parse.urljoin(self.api_base, method)
        return requests.get(url, *args, **kwargs)
    
    def api_call_paginated(
        self,
        method: str,
        slug: str,
        *args: Any,
        params: Dict[str, Any] = {},
        t: Optional[Callable] = None,
        **kwargs: Any
    ) -> "PaginatedResult[T]":
        """
        get a full list that will be returned in parts
        `slug` is the key in the JSON response that is to be concatenated
        """
        
        if not t:
            t = cast(Callable[[JSONData], T], lambda x: x)
        
        return PaginatedResult(self, method, slug, *args, params=params, t=t, **kwargs)
    
    def get_image(self, image_id: int) -> Image:
        "load details for a given image_id"
        
        response = self.api_call(f"images/{image_id:d}")
        response.raise_for_status()
        return Image(response.json()["image"])
    
    def get_tag(self, tag_slug: str) -> Tag:
        "load details for a given slug"
        
        self.validate_tag_slug(tag_slug)
        
        response = self.api_call(f"tags/{urllib.parse.quote(tag_slug)}")
        response.raise_for_status()
        return Tag(response.json()["tag"])
    
    SLUG_LOOKUPS = {
        ".": "dot",
        "-": "dash",
        ":": "colon",
        "/": "fwslash",
    }
    SLUG_ESCAPES = list(SLUG_LOOKUPS.values())
    OPTIONAL_ESCAPES = "'()"
    
    @classmethod
    def validate_tag_slug(clz, tag: str) -> bool:
        if not tag:
            raise ValueError("Empty string is not a valid tag")
        
        rest = tag
        while rest:
            c = rest[0]
            if c in string.ascii_lowercase or c in string.digits:
                rest = rest[1:]
                continue
            if c in "_+" or c in clz.OPTIONAL_ESCAPES:
                rest = rest[1:]
                continue
            if c in "-":
                try:
                    pos = rest[1:].index("-")
                except ValueError as e:
                    raise ValueError(f"Not a complete escape sequence: {rest!r}") from e
                
                escape = rest[1:pos + 1]
                if escape not in clz.SLUG_ESCAPES:
                    raise ValueError(f"Not a valid escape sequence: {rest[:pos+2]!r}")
                
                rest = rest[pos + 2:]
                continue
            if c == "%":
                if len(rest) < 3:
                    raise ValueError("percent followed by less than two hexdigits")
                if rest[1] in string.hexdigits and rest[2] in string.hexdigits:
                    rest = rest[3:]
                    continue
                raise ValueError("percent followed by less than two hexdigits")
            
            raise ValueError(f"Invalid character {c!r} in tag {tag!r}")
        
        return True
    
    @classmethod
    def tag_to_slug(clz, name: str, optional_escapes: bool = False) -> str:
        """
        convert a tag name to its slug
        
        Note: some characters are optionally encoded, but not always.
        You have to check for each which version to apply. :-(
        """
        
        slug = ""
        for c in name.lower():
            if c in string.ascii_lowercase or c in string.digits:
                slug += c
            elif c in "_":
                slug += c
            elif c in clz.OPTIONAL_ESCAPES:
                # optional escapes - might be replaced, but we can't say for sure :(
                slug += urllib.parse.quote(c) if optional_escapes else c
            elif c == " ":
                slug += "+"
            elif c in clz.SLUG_LOOKUPS:
                slug += "-{}-".format(clz.SLUG_LOOKUPS[c])
            else:
                slug += urllib.parse.quote(c)
        return slug
    
    def get_filter(self, filter_id: int) -> Filter:
        "load details for a given filter_id"
        
        response = self.api_call(f"filters/{filter_id:d}")
        response.raise_for_status()
        return Filter(response.json()["filter"])
    
    def search_images(
        self,
        query: str,
        sort_field: Optional[str] = None,
        sort_direction: Optional[str] = None,
        filter_id: Optional[int] = None,
        per_page: Optional[int] = None,
        key: Optional[str] = None
    ) -> "PaginatedResult[Image]":
        "search for images matching a query. returns an iterable of images."
        
        params: Dict[str, Any] = {"q": query}
        if sort_field:
            params["sf"] = sort_field
        if sort_direction:
            params["sd"] = sort_direction
        if filter_id is not None:
            params["filter_id"] = int(filter_id)
        if per_page:
            params["per_page"] = int(per_page)
        if key is not None:
            params["key"] = key
        
        return self.api_call_paginated("search/images", "images", params=params, t=Image)
    
    def search_tags(self, query: str, per_page: Optional[int] = None) -> "PaginatedResult[Tag]":
        "search for tags matching a query. returns an iterable of tags."
        
        params: Dict[str, Any] = {"q": query}
        if per_page:
            params["per_page"] = int(per_page)
        return self.api_call_paginated("search/tags", "tags", params=params, t=Tag)
    
    def search_filters(self, query: str, per_page: Optional[int] = None) -> "PaginatedResult[Filter]":
        "search for filters matching a query. returns an iterable of filters."
        
        params: Dict[str, Any] = {"q": query}
        if per_page:
            params["per_page"] = int(per_page)
        return self.api_call_paginated("search/filters", "filters", params=params, t=Filter)


class PaginatedResult(Iterator[T], Generic[T]):
    results: List[JSONData]
    total: int
    
    def __init__(
        self,
        site: Site,
        method: str,
        slug: str,
        *args: Any,
        params: Dict[str, Any] = {},
        t: Optional[Callable],
        **kwargs: Any,
    ):
        self.site = site
        self.method = method
        self.slug = slug
        self.params = params
        self.t = t if t else lambda x: x
        self.args = args
        self.kwargs = kwargs
        
        self.results = []
        self.fetch_next()
    
    @property
    def page(self) -> int:
        return int(self.params.get("page", 1))
    
    def __next__(self) -> T:
        if not self.results:
            self.fetch_next()
            if not self.results:
                raise StopIteration
        
        t = cast(Callable[[JSONData], T], self.t)
        return t(self.results.pop(0))
    
    def fetch_next(self) -> None:
        self.params["page"] = self.page + 1
        
        pause = 2
        while True:
            response = self.site.api_call(self.method, *self.args, params=self.params, **self.kwargs)
            if response.status_code != 429:
                break
            time.sleep(pause)
            pause *= 2
        
        response.raise_for_status()
        
        data = response.json()
        self.total = data["total"]
        self.results += data[self.slug]
    

