# Contributing

Install development dependencies and run the offline regression suite:

```sh
python -m pip install -e ".[dev]"
python -m pytest
```

Tests belong in `tests/`, manual verification tools in `tools/`, and usage
examples in `examples/`. Use synthetic fixtures so regression tests are
reproducible. The test suite blocks unmocked HTTP requests.

## Manual read-only verification

From the project directory, with a token file outside the repository:

```sh
python -m tools.verify_read_only --url "$CUDY_ROUTER_URL" --token-file "$CUDY_TOKEN_FILE"
```

The tool performs named status reads and reports structural types. Optional
`--include-config`, `--client-mac` and `--mesh-node` add selected reads.
Use `--cellular-interface` with a known interface for cellular status/statistics;
cellular data-plan settings also require `--include-config`. No interface is guessed.
The tool never sends mutations, scans or password-login requests. Optional
unsupported reads are reported separately; successful exit requires the core
system and device reads, not success for every optional method.

## API changes

Update the [API reference](docs/api-reference.md) when changing a public method.
Put RPC parameters and response shapes in the relevant operation guide, and
router-specific observations in [compatibility](docs/compatibility.md). Keep
the [read coverage checklist](docs/read-coverage.md) as an implementation tracker.

## Release checks

Build with `python -m build` and inspect both archives before release. Regression
tests and manual tools are included in the source distribution, not the library
wheel. Only intended project files should enter either archive.

Review the staged diff before committing.
