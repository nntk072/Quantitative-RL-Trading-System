# Static order charts

This package contains the static order-chart pipeline: chart entry points in
`charts.py`, per-trade window preparation in `window.py`, geometry in
`geometry.py`, backend drawing in `renderers.py`, visual overlays in
`overlays.py`, and event extraction in `events.py`.

The implementation dependency direction is `charts` → `window` → `geometry` and `events`; `geometry` and feature zone
extraction share data models, renderers consume geometry, overlays consume
events, and events own their source calculations. Package exports are lazy to keep importing the
plotting namespace from eagerly loading chart backends. The former module paths
remain compatibility shims.
