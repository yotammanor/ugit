import subprocess
from collections import defaultdict
from typing import Iterable
from typing_extensions import Unpack
from tempfile import NamedTemporaryFile as Temp
from ugit import base

from . import data


def compare_trees(*trees: Unpack[base.TreeMap]) -> Iterable[tuple[base.Path, Unpack[list[base.OID]]]]:
    entries = defaultdict(lambda: [None] * len(trees))
    for i, tree in enumerate(trees):
        for path, oid in tree.items():
            entries[path][i] = oid

    for path, oids in entries.items():
        yield path, *oids


def diff_trees(t_from: base.TreeMap, t_to: base.TreeMap) -> bytes:
    output = b''
    for path, o_from, o_to in compare_trees(t_from, t_to):
        if o_from != o_to:
            output += diff_blobs(o_from, o_to, path)
    return output


def diff_blobs(o_from: base.OID, o_to: base.OID, path='blob'):
    with Temp() as f_from, Temp() as f_to:
        for oid, f in [(o_from, f_from), (o_to, f_to)]:
            if oid:
                f.write(data.get_object(oid))
                f.flush()

        with subprocess.Popen(
                ['diff', '--unified', '--show-c-function',
                 '--label', f'a/{path}', f_from.name,
                 '--label', f'b/{path}', f_to.name],
                stdout=subprocess.PIPE
        ) as proc:
            output, _ = proc.communicate()

        return output
