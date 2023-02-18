from typing import Dict, List, Optional, Sequence, Union

from . import utils

__all__ = ["Filter", "Image", "Tag", "Interaction", "JSONObject", "JSONArray", "JSONData"]

JSONObject = Dict[str, "JSONData"]
JSONArray = Sequence["JSONData"]
JSONData = Union[JSONObject, JSONArray, str, int, float, bool, None]


class Filter(utils.JSONClass):
    description: str
    hidden_complex: Optional[str]
    hidden_tag_ids: Sequence[int]
    id: int
    name: str
    public: bool
    spoilered_complex: Optional[str]
    spoilered_tag_ids: Sequence[int]
    system: bool
    user_count: int
    user_id: Optional[int]


class Image(utils.JSONClass):
    animated: bool
    aspect_ratio: float
    comment_count: int
    created_at: str
    deletion_reason: Optional[str]
    description: str
    downvotes: int
    duplicate_of: Optional[int]
    duration: float
    faves: int
    first_seen_at: str
    format: str
    height: int
    hidden_from_users: bool
    id: int
    intensities: Optional[Dict[str, float]]
    mime_type: str
    name: str
    orig_sha512_hash: str
    processed: bool
    representations: Dict[str, str]
    score: int
    sha512_hash: str
    size: int
    source_url: str
    spoilered: bool
    tag_count: int
    tag_ids: List[int]
    tags: List[str]
    thumbnails_generated: bool
    updated_at: str
    uploader: Optional[str]
    uploader_id: Optional[int]
    upvotes: int
    view_url: str
    width: int
    wilson_score: float


class Tag(utils.JSONClass):
    class DNPEntry(utils.JSONClass):
        conditions: str
        created_at: str
        dnp_type: str
        id: int
        reason: Optional[str]
    
    aliased_tag: Optional[str]
    aliases: Sequence[str]
    category: Optional[str]
    description: str
    dnp_entries: List[DNPEntry]
    id: int
    images: int
    implied_by_tags: List[str]
    implied_tags: List[str]
    name: str
    name_in_namespace: str
    namespace: Optional[str]
    short_description: Optional[str]
    slug: str
    spoiler_image_uri: Optional[str]


class Interaction(utils.JSONClass):
    image_id: int
    interaction_type: str
    user_id: int
    value: str

