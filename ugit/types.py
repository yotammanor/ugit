from typing import TypeAlias, NamedTuple

Path: TypeAlias = str
OID: TypeAlias = str
TreeMap: TypeAlias = dict[Path, OID]
BlobTreeMap: TypeAlias = dict[Path, bytes]


class Commit(NamedTuple):
    tree: OID
    parent: OID
    message: str
