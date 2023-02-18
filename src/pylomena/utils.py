import abc

from typing import Any, Dict, List, Tuple, Type

__all__ = ["JSONClass", "get_class_name"]


class JSONClass(abc.ABC):
    def __init__(self, jsondata: Dict[str, Any]):
        for key, value in jsondata.items():
            key, value = self.convert(key, value)
            setattr(self, key, value)
    
    @classmethod
    def convert(clz: Type["JSONClass"], key: str, value: Any) -> Tuple[str, Any]:
        try:
            t = clz.__annotations__[key]
        except KeyError:
            return key, value
        
        if t == List:
            inner_t = t.__args__[0]
            value = [inner_t(i) for i in value]
        elif t.__module__ != "typing":
            value = t(value)
        return key, value
    

def get_class_name(clz: Type) -> str:
    module = clz.__module__
    if module == 'builtins':
        # avoid outputs like 'builtins.str'
        return clz.__qualname__
    return module + '.' + clz.__qualname__

