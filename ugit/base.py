import string

import ugit.types
from . import data, diff
from . import types

import itertools
import operator
import os

from collections import deque


def init():
    data.init()
    data.update_ref('HEAD', ugit.types.RefValue(symbolic=True, value='refs/heads/master'))


def get_branch_name():
    HEAD = data.get_ref('HEAD', deref=False)
    if not HEAD.symbolic:
        return None
    HEAD = HEAD.value
    assert HEAD.startswith('refs/heads'), f'expected HEAD to start with "refs/heads", found {HEAD}'
    return os.path.relpath(HEAD, 'refs/heads')


def checkout(name):
    oid = get_oid(name)
    commit_ = get_commit(oid)
    read_tree(commit_.tree)

    if is_branch(name):
        HEAD = ugit.types.RefValue(symbolic=True, value=f'refs/heads/{name}')
    else:
        HEAD = ugit.types.RefValue(symbolic=False, value=oid)

    data.update_ref("HEAD", HEAD, deref=False)


def iter_branch_names():
    for refname, _ in data.iter_refs('refs/heads/'):
        yield os.path.relpath(refname, 'refs/heads/')


def is_branch(name):
    return data.get_ref(f'refs/heads/{name}').value is not None


def get_commit(oid: types.OID) -> types.Commit:
    parents = []
    tree = None
    commit_ = data.get_object(oid, 'commit').decode()
    lines = iter(commit_.splitlines())
    for line in itertools.takewhile(operator.truth,
                                    lines):  # this works because there's an empty line between the key-value pairs and the message
        key, value = line.split(' ', 1)
        if key == 'tree':
            tree = value
        elif key == 'parent':
            parents.append(value)
        else:
            raise AssertionError(f'Unknown field {key}')

    assert tree is not None, 'Expected tree to be defined'
    message = '\n'.join(lines)
    return types.Commit(tree=tree, parents=parents, message=message)


def write_tree():
    index_as_tree = {}
    with data.get_index() as index:
        for path, oid in index.items():
            path = path.split('/')
            dirpath, filename = path[:-1], path[-1]
            current = index_as_tree
            # Find the dict for the dictionary of this file
            for dirname in dirpath:
                current = current.setdefault(dirname, {})
            current[filename] = oid

    def write_tree_recursive(tree_dict):
        entries = []
        for name, value in tree_dict.items():
            if type(value) is dict:
                type_ = 'tree'
                oid = write_tree_recursive(value)
            else:
                type_ = 'blob'
                oid = value
            entries.append((name, oid, type_))

        tree = ''.join(f'{type_} {oid} {name}\n'
                       for name, oid, type_
                       in sorted(entries))
        return data.hash_object(tree.encode(), 'tree')

    return write_tree_recursive(index_as_tree)


def _iter_tree_entries(oid):
    if not oid:
        return
    tree = data.get_object(oid, 'tree')
    for entry in tree.decode().splitlines():
        type_, oid, name = entry.split(' ', 2)
        yield type_, oid, name


def get_tree(oid: types.OID, base_path: types.Path = '') -> types.TreeMap:
    result = {}
    for type_, oid, name in _iter_tree_entries(oid):
        assert '/' not in name
        assert name not in ('..', '.')
        path = base_path + name
        if type_ == 'blob':
            result[path] = oid
        elif type_ == 'tree':
            result.update(get_tree(oid, f'{path}/'))
        else:
            raise AssertionError(f'Unknown tree entry {type_}')
    return result


def get_working_tree() -> types.TreeMap:
    result = {}
    for root, _, filenames in os.walk('.'):
        for filename in filenames:
            path = os.path.relpath(f'{root}/{filename}')
            if is_ignored(path) or not os.path.isfile(path):
                continue
            with open(path, 'rb') as f:
                fixed_path = path.replace('\\', '/')  # window fix
                result[fixed_path] = data.hash_object(f.read())
    return result


def read_tree(tree_oid):
    _empty_current_directory()
    for path, oid in get_tree(tree_oid, base_path='./').items():
        os.makedirs(os.path.dirname(path), exist_ok=True)
        with open(path, 'wb') as f:
            f.write(data.get_object(oid))


def _empty_current_directory():
    for root, dirnames, filenames in os.walk('.', topdown=False):
        for filename in filenames:
            path = os.path.relpath(f'{root}/{filename}')
            if is_ignored(path) or not os.path.isfile(path):
                continue
            os.remove(path)
        for dirname in dirnames:
            path = os.path.relpath(f'{root}/{dirname}')
            if is_ignored(path):
                continue
            try:
                os.rmdir(path)
            except (FileNotFoundError, OSError):
                pass  # ignored file in dir


def reset(oid):
    data.update_ref('HEAD', ugit.types.RefValue(symbolic=False, value=oid))


def create_branch(name, oid):
    data.update_ref(f'refs/heads/{name}', ugit.types.RefValue(symbolic=False, value=oid))


def create_tag(name, oid):
    data.update_ref(f'refs/tags/{name}', ugit.types.RefValue(symbolic=False, value=oid))


def get_merge_base(oid1: types.OID, oid2: types.OID) -> types.OID:
    parents1 = set(iter_commits_and_parents({oid1}))

    for oid in iter_commits_and_parents({oid2}):
        if oid in parents1:
            return oid

    assert False, "A merge base must exist"


def read_tree_merged(t_base: types.OID, t_head: types.OID, t_other: types.OID) -> None:
    _empty_current_directory()
    merged_tree = diff.merge_trees(
        get_tree(t_base),
        get_tree(t_head),
        get_tree(t_other)
    )
    for path, blob in merged_tree.items():
        os.makedirs(f'./{os.path.dirname(path)}', exist_ok=True)
        with open(path, 'wb') as f:
            f.write(blob)


def is_ancestor_of(commit_, maybe_ancestor):
    return maybe_ancestor in iter_commits_and_parents({commit_})


def merge(other):
    HEAD = data.get_ref('HEAD').value
    assert HEAD
    c_other = get_commit(other)
    merge_base = get_merge_base(other, HEAD)

    if merge_base == HEAD:
        read_tree(c_other.tree)
        data.update_ref('HEAD',
                        data.RefValue(symbolic=False, value=other))
        print('Fast-forward merge, no need to commit')
        return

    data.update_ref('MERGE_HEAD', data.RefValue(symbolic=False, value=other))

    c_base = get_commit(merge_base)
    c_HEAD = get_commit(HEAD)
    read_tree_merged(c_base.tree, c_HEAD.tree, c_other.tree)
    print('Merged in working tree\nPlease commit')


def commit(message):
    commit_ = f'tree {write_tree()}\n'

    HEAD = data.get_ref("HEAD").value
    if HEAD:
        commit_ += f'parent {HEAD}\n'

    MERGE_HEAD = data.get_ref('MERGE_HEAD').value
    if MERGE_HEAD:
        commit_ += f'parent {MERGE_HEAD}\n'
        data.delete_ref('MERGE_HEAD', deref=False)

    commit_ += '\n'
    commit_ += f'{message}\n'

    oid = data.hash_object(commit_.encode(), 'commit')
    data.update_ref("HEAD", ugit.types.RefValue(symbolic=False, value=oid))
    return oid


def get_oid(name):
    if name == '@':
        name = 'HEAD'

    refs_to_try = [
        f'{name}',
        f'refs/{name}',
        f'refs/tags/{name}',
        f'refs/heads/{name}'
    ]
    for ref in refs_to_try:
        if oid := data.get_ref(ref).value:
            return oid

    is_hex = all(c in string.hexdigits for c in name)
    if len(name) == 40 and is_hex:
        return name

    raise AssertionError(f'Unknown name {name}')


def iter_commits_and_parents(oids):
    oids = deque(oids)
    visited = set()

    while oids:
        oid = oids.popleft()
        if not oid or oid in visited:
            continue
        visited.add(oid)
        yield oid

        commit_ = get_commit(oid)
        oids.extendleft(commit_.parents[:1])
        oids.extend(commit_.parents[1:])


def iter_objects_in_commits(oids):
    visited = set()

    def iter_objects_in_tree(source_tree_oid):
        visited.add(source_tree_oid)
        yield source_tree_oid
        for type_, oid_, _ in _iter_tree_entries(source_tree_oid):
            if oid_ not in visited:
                if type_ == 'tree':
                    yield from iter_objects_in_tree(oid_)
                else:
                    visited.add(oid_)
                    yield oid_

    for oid in iter_commits_and_parents(oids):
        yield oid
        commit_ = get_commit(oid)
        if commit_.tree not in visited:
            yield from iter_objects_in_tree(commit_.tree)


def add(filenames):
    def add_file(filename):
        # Normalize path
        filename = os.path.relpath(filename).replace('\\', '/')
        with open(filename, 'rb') as f:
            oid = data.hash_object(f.read())
        index[filename] = oid

    def add_directory(dirname):
        for root, _, filenames_inner in os.walk(dirname):
            for filename_inner in filenames_inner:
                path = os.path.relpath(f'{root}/{filename_inner}').replace('\\', '/')
                if is_ignored(path) or not os.path.isfile(path):
                    continue
                add_file(path)

    with data.get_index() as index:
        for name in filenames:
            if os.path.isfile(name):
                add_file(name)
            elif os.path.isdir(name):
                add_directory(name)


def is_ignored(path):
    path = path.replace('\\', '/')
    return (
            ('.ugit' in path.split('/')) or
            ('venv' in path.split('/')) or
            ('ugit.egg-info' in path.split('/')) or
            ('__pycache__' in path.split('/')) or
            ('.idea' in path.split('/')) or
            ('.git' in path.split('/'))
    )
