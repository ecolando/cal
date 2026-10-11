"""Manually scrape assignments locally and publish them to the site.

Usage:
    py update.py            # scrape, commit data/assignments.js, push to main + github-pages
    py update.py --no-push  # scrape and write data/assignments.js only

Credentials are read from environment variables, then from a gitignored
`.env` file (KEY=value per line), and finally prompted for if still missing.
"""

import os
import sys
import argparse
import subprocess
from getpass import getpass

ROOT = os.path.dirname(os.path.abspath(__file__))
os.chdir(ROOT)
sys.path.insert(0, ROOT)

from src.common import utils
from src.modules import *


def load_env_file(path='.env'):
    if not os.path.exists(path):
        return
    with open(path, 'r', encoding='utf-8') as file:
        for line in file:
            line = line.strip()
            if not line or line.startswith('#') or '=' not in line:
                continue
            key, value = line.split('=', 1)
            os.environ.setdefault(key.strip(), value.strip().strip('"\''))


def ensure_credentials(module_names):
    """Prompts for missing credentials and returns the ones that were entered."""
    entered = {}
    for name in module_names:
        user_env, password_env = name + '_USER', name + '_PASSWORD'
        try:
            if not os.environ.get(user_env):
                entered[user_env] = os.environ[user_env] = input(f'{user_env}: ')
            if not os.environ.get(password_env):
                entered[password_env] = os.environ[password_env] = getpass(f'{password_env}: ')
        except EOFError:
            sys.exit(f'\nMissing {user_env}/{password_env}: add them to .env '
                     'or run this script in a terminal that accepts input')
    return entered


def save_env_file(values, path='.env'):
    """Adds or replaces VALUES in the .env file, keeping any other lines."""
    lines = []
    if os.path.exists(path):
        with open(path, 'r', encoding='utf-8') as file:
            lines = [l for l in file.read().splitlines()
                     if l.split('=', 1)[0].strip() not in values]
    lines += [f'{key}={value}' for key, value in values.items()]
    with open(path, 'w', encoding='utf-8') as file:
        file.write('\n'.join(lines) + '\n')
    print(f'Saved login to {path}')


def git(*args):
    print('$ git ' + ' '.join(args))
    return subprocess.run(['git', *args], check=True)


def publish():
    git('add', os.path.join('data', 'assignments.js'))
    staged = subprocess.run(['git', 'diff', '--cached', '--quiet'])
    if staged.returncode == 0:
        print('No changes to assignments, nothing to commit')
    else:
        git('commit', '-m', 'Updated assignments (manual)')
    git('push', 'origin', 'main')
    git('push', '-f', 'origin', 'main:github-pages')


def main():
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument('--no-push', action='store_true', help='only write data/assignments.js')
    args = parser.parse_args()

    load_env_file()
    entered = ensure_credentials(['GRADESCOPE'])

    assignments = {}
    for module in [Gradescope()]:
        module.run(assignments)
        # Only remember credentials once they are known to work
        if module.initialized:
            to_save = {k: v for k, v in entered.items() if k.startswith(module.name + '_')}
            if to_save:
                save_env_file(to_save)

    count = sum(len(v) for v in assignments.values()) if assignments else 0
    if count == 0:
        print('No assignments found; leaving existing data untouched')
        return 1

    utils.save_data('assignments', assignments)
    print(f'Saved {count} assignments to data/assignments.js')

    if not args.no_push:
        publish()
    return 0


if __name__ == '__main__':
    sys.exit(main())
