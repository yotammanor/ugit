from typing import TypeAlias, NamedTuple

Path: TypeAlias = str  # a path in the filesystem
OID: TypeAlias = str  # hash
TreeMap: TypeAlias = dict[Path, OID]
BlobTreeMap: TypeAlias = dict[Path, bytes]


class Commit(NamedTuple):
    tree: OID
    parents: list[OID]
    message: str


class RefValue(NamedTuple):
    symbolic: bool
    value: OID
