"""Start the gallery with optional, Git-ignored local environment settings."""
import os
from pathlib import Path
import runpy

ROOT = Path(__file__).resolve().parent


def load_local_environment():
    path = ROOT / '.env.local'
    if not path.exists():
        return
    for line in path.read_text().splitlines():
        line = line.strip()
        if not line or line.startswith('#'):
            continue
        key, separator, value = line.partition('=')
        key = key.strip()
        if not separator or not key.isidentifier():
            raise ValueError('Invalid setting in .env.local')
        value = value.strip()
        if len(value) >= 2 and value[0] == value[-1] and value[0] in ('"', "'"):
            value = value[1:-1]
        os.environ.setdefault(key, value)


if __name__ == '__main__':
    load_local_environment()
    os.environ.setdefault('HOST', '0.0.0.0')
    os.environ.setdefault('PORT', '8080')
    runpy.run_path(str(ROOT / 'app.py'), run_name='__main__')
