# Market-data commands

`market_data/commands/` implements data discovery and preparation entrypoints.
The commands prepare configured data, discover symbols, and prebuild caches
for resolved experiment runs. They coordinate the data APIs; ingestion,
transforms, splits, and cache identity stay owned by their respective
`market_data/` modules.

Preparation and cache building can use substantial storage and compute. Use
the documented data workflow and keep source, date range, and configuration
identity with produced caches. Focused tests are in `tests/unit/market_data/`
and `tests/integration/`.
