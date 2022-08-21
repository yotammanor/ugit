import string

from . import data
import itertools
import operator
import os

from collections import deque, namedtuple

Commit = namedtuple('Commit', ['tree', 'parent', 'message'])


def create_tag(name, oid):
    data.update_ref(f'refs/tags/{name}', oid)


def checkout(oid):
    commit_ = get_commit(oid)
    read_tree(commit_.tree)
    data.update_ref("HEAD", oid)


def get_commit(oid):
    parent = None
    tree = None
    commit_ = data.get_object(oid, 'commit').decode()
    lines = iter(commit_.splitlines())
    for line in itertools.takewhile(operator.truth,
                                    lines):  # this works because there's an empty line between the key-value pairs and the message
        key, value = line.split(' ', 1)
        if key == 'tree':
            tree = value
        elif key == 'parent':
            parent = value
        else:
            raise AssertionError(f'Unknown field {key}')

    assert tree is not None, 'Expected tree to be defined'
    message = '\n'.join(lines)
    return Commit(tree=tree, parent=parent, message=message)


def write_tree(directory='.'):
    entries = []
    with os.scandir(directory) as it:
        for entry in it:
            full = f'{directory}/{entry.name}'
            if is_ignored(full):
                continue
            if entry.is_file(follow_symlinks=False):
                type_ = 'blob'
                with open(full, 'rb') as f:
                    oid = data.hash_object(f.read())
            elif entry.is_dir(follow_symlinks=False):
                type_ = 'tree'
                oid = write_tree(full)
            entries.append((entry.name, oid, type_))
    tree = ''.join(f'{type_} {oid} {name}\n'
                   for name, oid, type_
                   in sorted(entries))
    return data.hash_object(tree.encode(), 'tree')


def _iter_tree_entries(oid):
    if not oid:
        return
    tree = data.get_object(oid, 'tree')
    for entry in tree.decode().splitlines():
        type_, oid, name = entry.split(' ', 2)
        yield type_, oid, name


def get_tree(oid, base_path=''):
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


def commit(message):
    commit_ = f'tree {write_tree()}\n'

    HEAD = data.get_ref("HEAD")
    if HEAD:
        commit_ += f'parent {HEAD}\n'

    commit_ += '\n'
    commit_ += f'{message}\n'

    oid = data.hash_object(commit_.encode(), 'commit')
    data.update_ref("HEAD", oid)
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
        if oid := data.get_ref(ref):
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
        oids.appendleft(commit_.parent)


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
