from collections import defaultdict
from typing import Iterable
from typing_extensions import Unpack

from ugit import base


def compare_trees(*trees: Unpack[base.TreeMap]) -> Iterable[tuple[base.Path, Unpack[list[base.OID]]]]:
    entries = defaultdict(lambda: [None] * len(trees))
    for i, tree in enumerate(trees):
        for path, oid in tree.items():
            entries[path][i] = oid

    for path, oids in entries.items():
        yield path, *oids


def diff_trees(t_from: base.TreeMap, t_to: base.TreeMap) -> str:
    output = ''
    for path, o_from, o_to in compare_trees(t_from, t_to):
        if o_from != o_to:
            output += f'changed {path}\n'
    return output
