import os

from . import data


def write_tree(directory='.'):
    with os.scandir(directory) as it:
        for entry in it:
            full = f'{directory}/{entry.name}'
            if is_ignored(full):
                continue
            if entry.is_file(follow_symlinks=False):
                # todo: write the file to object store
                print(full)
            elif entry.is_dir(follow_symlinks=False):
                write_tree(full)
    # todo: actually create the tree object


def is_ignored(path):
    return (
            ('.ugit' in path.split('/')) or
            ('venv' in path.split('/')) or
            ('ugit.egg-info' in path.split('/')) or
            ('__pycache__' in path.split('/')) or
            ('.idea' in path.split('/')) or
            ('.git' in path.split('/'))
    )
