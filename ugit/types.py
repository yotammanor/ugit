from typing import TypeAlias, NamedTuple, Literal

Path: TypeAlias = str  # a path in the filesystem
OID: TypeAlias = str  # hash
TreeMap: TypeAlias = dict[Path, OID]
ObjectType: TypeAlias = Literal['blob', 'tree', 'commit']

class Commit(NamedTuple):
    tree: OID
    parents: list[OID]
    message: str


class RefValue(NamedTuple):
    symbolic: bool
    value: OID
