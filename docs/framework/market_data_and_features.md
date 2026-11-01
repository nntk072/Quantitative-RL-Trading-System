# Market data and features

## Overview

Configured bar ingestion feeds the feature pipeline. Feature rows retain their market timestamps and session eligibility; higher-timeframe inputs become visible only after their source candles close.

## Pipeline

```{mermaid}
flowchart LR
    S[CSV or broker bars] --> I[Ingestion and validation]
    I --> T[Timeframe transforms]
    T --> F[Indicators and structure]
    F --> N[Train-only normalization]
    N --> C[Versioned feature cache]
```

## Causality and normalization

The alignment contract forward-fills the latest completed higher-timeframe candle. It never backfills from a future close. Normalization is fitted on training rows only, then applies the last known training statistics to later rows.

See the [causal features tutorial](../learn/tutorials/02_causal_features.ipynb), [market data guide](../modules/market_data), [feature guide](../modules/features), and [feature catalog](../reference/feature_catalog).

## Extension points and reference

Use [add a feature](../how-to/add_feature), [prepare market data](../how-to/prepare_market_data), and the [Market Data API](../api/domains/data). Exact cache identity rules are in [cache and schema versions](../reference/cache_and_schema_versions).
