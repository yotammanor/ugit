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


def merge_trees(t_base: types.TreeMap, t_head: types.TreeMap, t_other: types.TreeMap) -> types.TreeMap:
    tree = {}
    for path, o_base, o_HEAD, o_other in compare_trees(t_base, t_head, t_other):
        merged_obj = merge_blobs(o_base, o_HEAD, o_other)
        tree[path] = data.hash_object(merged_obj)
    return tree


def merge_blobs(o_base: types.OID, o_head: types.OID, o_other: types.OID) -> bytes:
    with Temp() as f_base, Temp() as f_HEAD, Temp() as f_other:
        for oid, f in [(o_base, f_base), (o_head, f_HEAD), (o_other, f_other)]:
            if oid:
                f.write(data.get_object(oid))
                f.flush()

        with subprocess.Popen(
                [
                    'diff3', '-m',
                    '-L', 'HEAD', f_HEAD.name,
                    '-L', 'BASE', f_base.name,
                    '-L', 'MERGE_HEAD', f_other.name
                ], stdout=subprocess.PIPE
        ) as proc:
            output, _ = proc.communicate()
            assert proc.returncode in (0, 1)

        return output
