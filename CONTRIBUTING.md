# Contributing

Install development dependencies and run the offline regression suite:

```sh
python -m pip install -e ".[dev]"
python -m pytest
```

Tests belong in `tests/`, reusable manual verification tools in `tools/`, and
end-user usage examples in `examples/`. Keep synthetic fixtures reproducible;
never include router tokens, passwords, real client inventories or private
configuration. The unit suite blocks unmocked HTTP requests.

Optional dashboard dependencies and browser/graph checks are described in the
[dashboard guide](dashboard/README.md). They use synthetic data, not routers.

## Manual read-only verification

From the project directory, with a token file outside the repository:

```sh
python -m tools.verify_read_only --url "$CUDY_ROUTER_URL" --token-file "$CUDY_TOKEN_FILE"
```

The tool performs named status reads and reports structural types. Optional
`--include-config`, `--client-mac` and `--mesh-node` add explicitly selected
reads. Configuration can contain credentials even if the report omits them.
The tool never sends mutations, scans or password-login requests. Optional
unsupported reads are reported separately; successful exit requires the core
system and device reads, not success for every optional method.

## Change and publication checks

Document parameter structures, response types and compatibility limits in
standalone terms. Brief attribution to app or web-interface behavior is useful;
public docs should describe usable contracts without requiring external source files.

Build with `python -m build` and inspect both archives before release. Regression
tests and manual tools are included in the source distribution, not the library
wheel. Only intended project files should enter either archive.

Review the staged diff before committing. Ignore rules do not untrack files
that were already committed, and removing a file later does not remove history.
