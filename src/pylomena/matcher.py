"""
A port and modification of the search_parser library for performing client-side filtering.

Ported from https://github.com/philomena-dev/philomena/blob/master/assets/js/match_query.js
"""

import abc
import dateutil.parser
import re
import Levenshtein
import math
import time

from datetime import datetime, timezone, timedelta
from dateutil.relativedelta import relativedelta
from typing import cast, Callable, Iterable, List, Optional, Sequence, Tuple, Union

from . import api, utils
from .types import Image, Interaction

__all__ = ["parse_search", "ParseError"]

TOKEN_LIST: Sequence[Tuple[str, re.Pattern]] = (
    ('fuzz', re.compile(r"^~(?:\d+(\.\d+)?|\.\d+)")),
    ('boost', re.compile(r"^\^[-+]?\d+(\.\d+)?")),
    ('quoted_lit', re.compile(r'^\s*"(?:[^"]|\\")+"')),
    ('lparen', re.compile(r"^\s*\(\s*")),
    ('rparen', re.compile(r"^\s*\)\s*")),
    ('and_op', re.compile(r"^\s*(?:&&|AND)\s+")),
    ('and_op', re.compile(r"^\s*,\s*")),
    ('or_op', re.compile(r"^\s*(?:\|\||OR)\s+")),
    ('not_op', re.compile(r"^\s*NOT(?:\s+|(?=\())")),
    ('not_op', re.compile(r"^\s*[!-]\s*")),
    ('space', re.compile(r"^\s+")),
    ('word', re.compile(r"^(?:[^\s,()^~]|\\[\s,()^~])+")),
    ('word', re.compile(r"^(?:[^\s,()]|\\[\s,()])")),
)


NUMBER_FIELDS = (
    'id', 'width', 'height', 'aspect_ratio', 'comment_count',
    'score', 'upvotes', 'downvotes', 'faves', 'tag_count',
)

DATE_FIELDS = ('created_at', )
LITERAL_FIELDS = (
    'tags', 'orig_sha512_hash', 'sha512_hash',
    'score', 'uploader', 'source_url', 'description',
)


class ParseError(ValueError):
    pass


class SearchOperand(abc.ABC):
    @abc.abstractmethod
    def match(self, target: Image, interactions: Optional[Sequence[Interaction]] = None) -> bool:
        raise NotImplementedError


class SearchTerm(SearchOperand):
    raw_term: str
    term: Union[str, re.Pattern, float, datetime, Tuple[datetime, datetime]]
    fuzz: Optional[float]
    boost: Optional[float]
    
    def __init__(self, term: str):
        self.term = self.raw_term = term.strip()
        self.parsed = False
        self.fuzz = None
        self.boost = None
        self.wildcardable = False
    
    def __repr__(self) -> str:
        clzname = utils.get_class_name(type(self))
        return f"{clzname}({self.raw_term!r})"
    
    def append(self, substr: str) -> None:
        self.raw_term += substr
        self.term = self.raw_term
        self.parsed = False
    
    def parse_range_field(self, field: str) -> Optional[Tuple[str, str, str]]:
        if field in NUMBER_FIELDS:
            return (field, "eq", "number")
        
        if field in DATE_FIELDS:
            return (field, "eq", "date")
        
        match = re.match(r"^(\w+)\.([lg]te?|eq)$", field)
        if match:
            if match[1] in NUMBER_FIELDS:
                return (match[1], match[2], "number")
            if match[1] in DATE_FIELDS:
                return (match[1], match[2], "date")
        
        return None
    
    def parse_relative_date(self, date_val: str, qual: str) -> Tuple[Union[datetime, Tuple[datetime, datetime]], str]:
        match = re.search(r"(\d+) (second|minute|hour|day|week|month|year)s? ago", date_val)
        bounds = {
            "second": 1,
            "minute": 60,
            "hour": 3600,
            "day": 86400,
            "week": 604800,
            "month": 2592000,
            "year": 31536000,
        }
        
        if not match:
            raise ParseError(f"Cannot parse date string: {date_val!r}")
        
        amount = int(match[1], 10)
        scale = bounds[match[2]]
        
        now = time.time()
        bottom_date = datetime.fromtimestamp(now - (amount * scale), tz=timezone.utc).astimezone()
        top_date = datetime.fromtimestamp(now - ((amount - 1) * scale), tz=timezone.utc).astimezone()
        
        if qual == "lte" or qual == "lt":
            return (bottom_date, "lt")
        if qual == "gte" or qual == "gt":
            return (bottom_date, "gte")
        
        return ((bottom_date, top_date), "eq")
    
    def parse_absolute_date(self, date_val: str, qual: str) -> Tuple[Union[datetime, Tuple[datetime, datetime]], str]:
        PARSE_RES = [
            re.compile(r"^(\d{4})"),
            re.compile(r"^-(\d{2})"),
            re.compile(r"^-(\d{2})"),
            re.compile(r"^(?:\s+|T|t)(\d{2})"),
            re.compile(r"^:(\d{2})"),
            re.compile(r"^:(\d{2})"),
        ]
        
        if not date_val:
            raise ParseError("Empty term")
        
        timezone_offset = [0, 0]
        time_data = [0, 1, 1, 0, 0, 0]
        orig_date_val = date_val
        local_date_val = date_val
        
        match = re.search(r"([+-])(\d{2}):(\d{2})$", local_date_val)
        if match:
            timezone_offset[0] = int(match[2], 10)
            timezone_offset[1] = int(match[3], 10)
            
            if match[1] == "-":
                timezone_offset[0] *= -1
                timezone_offset[1] *= -1
            
            local_date_val = local_date_val[:-6]
        elif local_date_val[-1].lower() == "z":
            local_date_val = local_date_val[:-1]
        
        for i, regex in enumerate(PARSE_RES):
            if not local_date_val:
                i -= 1
                break
            
            match = regex.match(local_date_val)
            if not match:
                raise ParseError(f"Cannot parse date string: {orig_date_val!r}")
            
            time_data[i] = int(match[1], 10)
            local_date_val = local_date_val[match.end(0):]
        
        if local_date_val:
            raise ParseError(f"Cannot parse date string: {orig_date_val!r}")
        
        tz = timezone(timedelta(hours=timezone_offset[0], minutes=timezone_offset[1]))
        time_obj = datetime(
            time_data[0],
            time_data[1],
            time_data[2],
            time_data[3],
            time_data[4],
            time_data[5],
            tzinfo=tz,
        )
        
        DELTAS = (
            relativedelta(years=1),
            relativedelta(months=1),
            relativedelta(days=1),
            relativedelta(hours=1),
            relativedelta(minutes=1),
            relativedelta(seconds=1),
        )
        delta = DELTAS[i]
        
        if qual == "lte":
            return (time_obj + delta, "lt")
        if qual == "gte":
            return (time_obj, "gte")
        if qual == "lt":
            return (time_obj, "lt")
        if qual == "gt":
            return (time_obj + delta, "gte")
        
        bottom_date = time_obj
        top_date = time_obj + delta
        return ((bottom_date, top_date), "eq")
    
    def parse_date(self, date_val: str, qual: str) -> Tuple[Union[datetime, Tuple[datetime, datetime]], str]:
        try:
            return self.parse_absolute_date(date_val, qual)
        except ParseError:
            return self.parse_relative_date(date_val, qual)
    
    def parse(self) -> None:
        if self.parsed:
            return
        self.term = self.raw_term
        
        self.wildcardable = not self.fuzz and not re.match(r'^"([^"]|\\")+"$', self.term)
        
        if not self.wildcardable and not self.fuzz:
            self.term = self.term[1:-1]
        
        self.term = self._normalize_term()
        
        # N.B.: For the purposes of this parser, boosting effects are ignored.
        
        # Default.
        self.term_space = "tags"
        self.term_type = "literal"
        
        match_arr = self.term.split(":")
        
        if len(match_arr) > 1:
            candidate_term_space = match_arr[0]
            term_candidate = ":".join(match_arr[1:])
            range_parsing = self.parse_range_field(candidate_term_space)
            
            if range_parsing:
                self.term_space = range_parsing[0]
                self.term_type = range_parsing[2]
                
                if self.term_type == "date":
                    self.term, self.compare = self.parse_date(term_candidate, range_parsing[1])
                else:
                    self.term = float(term_candidate)
                    self.compare = range_parsing[1]
                
                self.wildcardable = False
            elif candidate_term_space in LITERAL_FIELDS:
                self.term_type = "literal"
                self.term = term_candidate
                self.term_space = candidate_term_space
            elif candidate_term_space == "my":
                self.term_type = "my"
                self.term_space = term_candidate
        
        if self.wildcardable:
            # Transforms wildcard match into regular expression.
            # A custom NFA with caching may be more sophisticated but not
            # likely to be faster.
            term = cast(str, self.term)
            
            term = re.sub(r"([.+^$[\]\\(){}|-])", r'\\\1', term)
            term = re.sub(r"([^\\]|[^\\](?:\\\\)+)\*", r'\1.*', term)
            term = re.sub(r"^(?:\\\\)*\*", '.*', term)
            term = re.sub(r"([^\\]|[^\\](?:\\\\)+)\?", r'\1.?', term)
            term = re.sub(r"^(?:\\\\)*\?", '.?', term)
            
            self.term = re.compile(f"^{term}$", flags=re.I)
        
        self.parsed = True
    
    def _normalize_term(self) -> str:
        term = cast(str, self.term)
        if not self.wildcardable:
            return term
        
        return re.sub(r"\\([^*?])", r"\1", term)
    
    def fuzzy_match(self, target_str: str) -> bool:
        if not isinstance(self.term, str):
            raise TypeError("self.term is not a str")
        
        if self.fuzz:
            if self.fuzz < 1.0:
                target_distance = len(target_str) * (1.0 - self.fuzz)
            else:
                target_distance = self.fuzz
        else:
            target_distance = 0
        
        distance = Levenshtein.distance(self.term, target_str.lower())
        
        return distance <= target_distance
    
    def exact_match(self, target_str: str) -> bool:
        if not isinstance(self.term, str):
            raise TypeError("self.term is not a str")
        
        return self.term.lower() == target_str.lower()
    
    def wildcard_match(self, target_str: str) -> bool:
        if not isinstance(self.term, re.Pattern):
            raise TypeError("self.term is not a regex")
        
        return bool(self.term.match(target_str))
    
    def interaction_match(
        self,
        image_id: int,
        type: str,
        interaction: Optional[str],
        interactions: Sequence[Interaction],
    ) -> bool:
        return any(
            v.image_id == image_id and v.interaction_type == type and (interaction is None or v.value == interaction)
            for v in interactions
        )
    
    def match(self, target: Image, interactions: Optional[Sequence[Interaction]] = None) -> bool:
        if not self.parsed:
            self.parse()
        
        comp_func: Callable[[str], bool]
        
        if self.term_type == "literal":
            if self.fuzz:
                comp_func = self.fuzzy_match
            elif self.wildcardable:
                comp_func = self.wildcard_match
            else:
                comp_func = self.exact_match
            
            if self.term_space == "tags":
                return any(comp_func(tag) for tag in target.tags)
            return comp_func(getattr(target, self.term_space))
        
        if self.term_type == "my":
            # Should work with most my:conditions except watched.
            
            if interactions is None:
                # no data, fall back
                return False
            
            if self.term_space == "faves":
                return self.interaction_match(target.id, "faved", None, interactions)
            if self.term_space == "upvotes":
                return self.interaction_match(target.id, "voted", "up", interactions)
            if self.term_space == "downvotes":
                return self.interaction_match(target.id, "voted", "down", interactions)
            
            # Other my: interactions aren't supported, return false to prevent them from triggering spoiler.
            return False
        
        if self.term_type == "date":
            date = dateutil.parser.isoparse(getattr(target, self.term_space))
            # The open-left, closed-right date range specified by the
            # date/time format limits the types of comparisons that are
            # done compared to numeric ranges.
            if self.compare == "lt":
                return cast(datetime, self.term) > date
            if self.compare == "gte":
                return cast(datetime, self.term) <= date
            
            bottom, top = cast(Tuple[datetime, datetime], self.term)
            return bottom <= date and top > date
        
        # Range matching.
        number = float(getattr(target, self.term_space))
        if math.isnan(number):
            return False
        term = cast(float, self.term)
        
        if self.fuzz:
            return term <= number + self.fuzz and term + self.fuzz >= number
        
        if self.compare == "lt":
            return number < term
        if self.compare == "gt":
            return number > term
        if self.compare == "lte":
            return number <= term
        if self.compare == "gte":
            return number >= term
        return term == number


class NotOperator(SearchOperand):
    def __init__(self, op: SearchOperand):
        self.op = op
    
    def __repr__(self) -> str:
        clzname = utils.get_class_name(type(self))
        return f"{clzname}({self.op!r})"
    
    def match(self, target: Image, interactions: Optional[Sequence[Interaction]] = None) -> bool:
        return not self.op.match(target, interactions)


class AndOperator(SearchOperand):
    def __init__(self, op1: SearchOperand, op2: SearchOperand):
        self.op1 = op1
        self.op2 = op2
    
    def __repr__(self) -> str:
        clzname = utils.get_class_name(type(self))
        return f"{clzname}({self.op1!r}, {self.op2!r})"
    
    def match(self, target: Image, interactions: Optional[Sequence[Interaction]] = None) -> bool:
        return self.op1.match(target, interactions) and self.op2.match(target, interactions)


class OrOperator(SearchOperand):
    def __init__(self, op1: SearchOperand, op2: SearchOperand):
        self.op1 = op1
        self.op2 = op2
    
    def __repr__(self) -> str:
        clzname = utils.get_class_name(type(self))
        return f"{clzname}({self.op1!r}, {self.op2!r})"
    
    def match(self, target: Image, interactions: Optional[Sequence[Interaction]] = None) -> bool:
        return self.op1.match(target, interactions) or self.op2.match(target, interactions)


def generate_lex_array(search_str: str) -> List[Union[SearchTerm, str]]:
    op_queue: List[str] = []
    group_negate: List[bool] = []
    token_stack: List[Union[SearchTerm, str]] = []
    search_term: Optional[SearchTerm] = None
    boost: Optional[float] = None
    fuzz: Optional[float] = None
    lparen_ctr: int = 0
    negate: bool = False
    boost_fuzz_str: str = ""
    local_search_str: str = search_str
    
    while local_search_str:
        for token_name, token_re in TOKEN_LIST:
            match = token_re.match(local_search_str)
            
            if match:
                match_str = match[0]
                
                if search_term and (
                    token_name in ("and_op", "or_op") or token_name == "rparen" and lparen_ctr == 0
                ):
                    # Set options.
                    search_term.boost = boost
                    search_term.fuzz = fuzz
                    # Push to stack
                    token_stack.append(search_term)
                    # Reset term and options data.
                    search_term = None
                    fuzz = None
                    boost = None
                    boost_fuzz_str = ""
                    lparen_ctr = 0
                    if negate:
                        token_stack.append("not_op")
                        negate = False
                
                if token_name == "and_op":
                    while op_queue and op_queue[0] == "and_op":
                        token_stack.append(op_queue.pop(0))
                    op_queue.insert(0, "and_op")
                elif token_name == "or_op":
                    while op_queue and op_queue[0] in ("and_op", "or_op"):
                        token_stack.append(op_queue.pop(0))
                    op_queue.insert(0, "or_op")
                elif token_name == "not_op":
                    if search_term:
                        # We're already inside a search term, so it does not apply, obv.
                        search_term.append(match_str)
                    else:
                        negate = not negate
                elif token_name == "lparen":
                    if search_term:
                        # If we are inside the search term, do not error
                        # out just yet; instead, consider it as part of
                        # the search term, as a user convenience.
                        search_term.append(match_str)
                        lparen_ctr += 1
                    else:
                        op_queue.insert(0, "lparen")
                        group_negate.append(negate)
                        negate = False
                elif token_name == "rparen":
                    if lparen_ctr > 0:
                        if search_term:
                            search_term.append(match_str)
                        else:
                            search_term = SearchTerm(match_str)
                        lparen_ctr -= 1
                    else:
                        while op_queue:
                            op = op_queue.pop(0)
                            if op == "lparen":
                                break
                            token_stack.append(op)
                        if group_negate and group_negate.pop():
                            token_stack.append("not_op")
                elif token_name == "fuzz":
                    fuzz = float(match_str[1:])
                    boost_fuzz_str += match_str
                elif token_name == "boost":
                    if search_term:
                        boost = float(match_str[1:])
                        boost_fuzz_str += match_str
                    else:
                        search_term = SearchTerm(match_str)
                elif token_name == "quoted_lit":
                    if search_term:
                        search_term.append(match_str)
                    else:
                        search_term = SearchTerm(match_str)
                elif token_name == "word":
                    if search_term:
                        if fuzz or boost:
                            boost = None
                            fuzz = None
                            search_term.append(boost_fuzz_str)
                            boost_fuzz_str = ""
                        search_term.append(match_str)
                    else:
                        search_term = SearchTerm(match_str)
                else:
                    # Append extra spaces within search terms.
                    if search_term:
                        search_term.append(match_str)
                
                # Truncate string and restart the token tests.
                local_search_str = local_search_str[match.end(0):]
                
                # Break since we have found a match
                break
    
    if search_term:
        search_term.boost = boost
        search_term.fuzz = fuzz
        token_stack.append(search_term)
    if negate:
        token_stack.append("not_op")
    
    if "rparen" in op_queue or "lparen" in op_queue:
        raise ParseError("Mismatched parentheses")
    
    token_stack += op_queue
    
    return token_stack


def parse_tokens(lexical_array: List[Union[SearchTerm, str]]) -> SearchOperand:
    operand_stack: List[SearchOperand] = []
    
    for token in lexical_array:
        if isinstance(token, SearchTerm):
            operand_stack.append(token)
        elif token in ("and_op", "or_op"):
            try:
                op2 = operand_stack.pop()
                op1 = operand_stack.pop()
            except IndexError:
                raise ParseError("Missing operand")
            if token == "and_op":
                operand_stack.append(AndOperator(op1, op2))
            else:
                operand_stack.append(OrOperator(op1, op2))
        elif token == "not_op":
            try:
                op = operand_stack.pop()
            except IndexError:
                raise ParseError("Missing operand")
            operand_stack.append(NotOperator(op))
        else:
            raise ParseError("Invalid operator")
    
    if len(operand_stack) > 1:
        raise ParseError("Missing operator")
    
    try:
        return operand_stack.pop()
    except IndexError:
        raise ParseError("Missing search term")


def parse_search(search: str) -> SearchOperand:
    return parse_tokens(generate_lex_array(search))


def main() -> None:
    import argparse
    parser = argparse.ArgumentParser()
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument("-q", "--query", action="store", help="Search Derpibooru for images")
    group.add_argument("image", nargs="?", type=int, help="Test a specific image")
    parser.add_argument("-t", "--test", action="store", required=True, help="Term to test")
    
    args = parser.parse_args()
    
    images: Iterable[Image]
    
    site = api.Site("https://derpibooru.org/")
    if args.query:
        images = site.search_images(args.query)
    else:
        images = [site.get_image(args.image)]
    
    test = parse_search(args.test)
    for image in images:
        # print(f"Image {image.id}:", ", ".join(image.tags))
        if test.match(image, []):
            print(f"Image {image.id} matches.")
        else:
            print(f"Image {image.id} does not match.")


if __name__ == "__main__":
    main()

