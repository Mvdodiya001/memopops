"""Host startup for an existing local or managed FalkorDB, without Docker."""
from __future__ import annotations

import argparse
import os
from pathlib import Path


def load_environment(path: Path) -> None:
    """Load literal project settings without replacing exported values or executing shell syntax."""
    if not path.is_file():
        raise ValueError(f"Configuration file not found: {path}. Copy .env.example or supply --env-file.")
    for line in path.read_text(encoding='utf-8-sig').splitlines():
        stripped = line.strip()
        if not stripped or stripped.startswith('#'):
            continue
        if '=' not in stripped:
            raise ValueError('Invalid configuration line: expected NAME=value')
        name, value = stripped.split('=', 1)
        name, value = name.strip(), value.strip()
        if not name.startswith(('FALKORDB_', 'MEMOPOPS_')):
            continue
        if len(value) >= 2 and value[0] == value[-1] and value[0] in ('"', "'"):
            value = value[1:-1]
        os.environ.setdefault(name, value)


def main() -> None:
    parser = argparse.ArgumentParser(description='Run the memopops API against your existing FalkorDB.')
    parser.add_argument('--env-file', type=Path, default=Path('.env'))
    parser.add_argument('--port', type=int, default=8001)
    args = parser.parse_args()
    if not 1 <= args.port <= 65535:
        parser.error('--port must be between 1 and 65535')
    try:
        load_environment(args.env_file)
        import json
        tokens = json.loads(os.environ.get('MEMOPOPS_AUTH_TOKENS', '{}'))
        if not isinstance(tokens, dict) or not tokens:
            raise ValueError('Configure MEMOPOPS_AUTH_TOKENS with workspace-scoped identities before starting.')
    except (ValueError, OSError) as exc:
        parser.error(str(exc))
    import uvicorn
    uvicorn.run('memopops.api:app', host='127.0.0.1', port=args.port)


if __name__ == '__main__':
    main()
