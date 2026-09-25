# Installation and development

Use Python 3.10 or later. From the repository root:

```sh
python3 -m venv .venv
. .venv/bin/activate
python -m pip install -e ".[dev]"
python -m pytest
```

On Windows, activate with `.venv\Scripts\activate`.
Runtime dependencies are declared in `pyproject.toml`; the requirements files
delegate to that metadata. No router credentials are needed for unit tests.

Build an sdist and wheel:

```sh
python -m build
```

Install the resulting wheel in a separate environment to verify packaging.
`cudypy/py.typed` is included for type-aware consumers. The optional dashboard
has separate dependencies and is not imported by the library.

For live use, supply your router's configured HTTP(S) origin and a
session token or password as described in [README.md](README.md). Token-based
connections bypass mDNS. Password connections can use a known salt when
multicast discovery is unavailable.

The dashboard has a separate [setup guide](dashboard/README.md).

