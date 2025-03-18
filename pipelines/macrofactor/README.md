# `knpl_macrofactor`: Process Macrofactor exports

* Expects a complete export
* Idempotent; adding the same data won't break anything
* You can export just a time window, or all data forever, from MacroFactor; this handles both

## Versioning

The project is versioned as 1.0.unixtime, like `1.0.1742334398`.
Use `buildver.py` to print a new version number representing the current second,
and build the package with that value like
`export KNPL_MACROFACTOR_BUILD_VERSION=1.0.1742334398`.
