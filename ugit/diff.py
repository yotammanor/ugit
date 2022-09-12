import subprocess
from collections import defaultdict
from typing import Iterable, TypeAlias, Literal
from typing_extensions import Unpack
from tempfile import NamedTemporaryFile as Temp

from . import types
from . import data


def compare_trees(*trees: Unpack[types.TreeMap]) -> Iterable[tuple[types.Path, Unpack[list[types.OID]]]]:
    entries = defaultdict(lambda: [None] * len(trees))
    for i, tree in enumerate(trees):
        for path, oid in tree.items():
            entries[path][i] = oid

    for path, oids in entries.items():
        yield path, *oids


def diff_trees(t_from: types.TreeMap, t_to: types.TreeMap) -> bytes:
    output = b''
    for path, o_from, o_to in compare_trees(t_from, t_to):
        if o_from != o_to:
            output += diff_blobs(o_from, o_to, path)
    return output


Action: TypeAlias = Literal['new_file', 'deleted', 'modified']


def iter_changed_files(t_from: types.TreeMap, t_to: types.TreeMap) -> Iterable[
    tuple[types.Path, Action]]:
    for path, o_from, o_to in compare_trees(t_from, t_to):
        if o_from != o_to:
            action = ('new_file' if not o_from else
                      'deleted' if not o_to else
                      'modified')
            yield path, action


def diff_blobs(o_from: types.OID, o_to: types.OID, path='blob'):
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
