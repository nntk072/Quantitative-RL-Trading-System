# Entry-idea opportunity counts

- Feature cache: `cache/data_modes/normal/train_test_2025_2026_v1/US100.cash_features_v29-wick-swings-body-invalidations_d662e1d4507f3377.parquet`
- Cached M1 rows: 630,787
- Timeframes: M1, M3, M5, M10, M15, M30, H1, H4, D1.
- Primary ideas: confirmed PO3 entry candidate, order-block retest, standard-deviation/Fibonacci entry, and FVG/IFVG retest.

## Annual totals

| year | m1_rows | idea_timeframe_active_bars_sum | idea_timeframe_episode_starts_sum | idea_timeframe_both_sides_bars_sum | unique_bars_any_idea | unique_bars_directionally_unambiguous | unique_bars_with_both_directions | cache_entry_idea_rows_with_both_directions | unique_bars_2plus_ideas | unique_bars_3plus_ideas | po3_signal_episode_starts | order_block_signal_episode_starts | standard_deviation_signal_episode_starts | fvg_ifvg_reaction_signal_episode_starts | po3_unique_bars | order_block_unique_bars | standard_deviation_unique_bars | fvg_ifvg_reaction_unique_bars |
| ---- | ------- | ------------------------------ | --------------------------------- | ---------------------------------- | -------------------- | ------------------------------------- | -------------------------------- | ------------------------------------------ | ----------------------- | ----------------------- | ------------------------- | --------------------------------- | ---------------------------------------- | --------------------------------------- | --------------- | ----------------------- | ------------------------------ | ----------------------------- |
| 2024 | 2730    | 4871                           | 912                               | 146                                | 2145                 | 1204                                  | 941                              | 941                                        | 1088                    | 273                     | 95                        | 119                               | 330                                      | 368                                     | 581             | 352                     | 1503                           | 1101                          |
| 2025 | 348702  | 826328                         | 120161                            | 39669                              | 306509               | 133782                                | 172727                           | 172727                                     | 192707                  | 68576                   | 14421                     | 17339                             | 42150                                    | 46251                                   | 77544           | 95533                   | 224074                         | 180353                        |
| 2026 | 279355  | 666786                         | 95297                             | 30572                              | 247931               | 109323                                | 138608                           | 138608                                     | 155410                  | 50956                   | 11172                     | 13500                             | 34375                                    | 36250                                   | 59145           | 69937                   | 184346                         | 147388                        |

## Counts by idea and timeframe

| year | idea               | timeframe | available | active_m1_bars | episode_starts | both_sides_active_m1_bars | long_active_m1_bars | short_active_m1_bars |
| ---- | ------------------ | --------- | --------- | -------------- | -------------- | ------------------------- | ------------------- | -------------------- |
| 2024 | PO3                | Any TF    | True      | 581            | 95             | 142                       | 302                 | 421                  |
| 2024 | Order block        | M1        | True      | 80             | 70             | 0                         | 37                  | 43                   |
| 2024 | Order block        | M3        | True      | 102            | 29             | 0                         | 33                  | 69                   |
| 2024 | Order block        | M5        | True      | 70             | 14             | 0                         | 40                  | 30                   |
| 2024 | Order block        | M10       | True      | 30             | 3              | 0                         | 0                   | 30                   |
| 2024 | Order block        | M15       | True      | 0              | 0              | 0                         | 0                   | 0                    |
| 2024 | Order block        | M30       | True      | 90             | 3              | 0                         | 0                   | 90                   |
| 2024 | Order block        | H1        | True      | 0              | 0              | 0                         | 0                   | 0                    |
| 2024 | Order block        | H4        | True      | 0              | 0              | 0                         | 0                   | 0                    |
| 2024 | Order block        | D1        | True      | 0              | 0              | 0                         | 0                   | 0                    |
| 2024 | Standard deviation | M1        | True      | 369            | 184            | 0                         | 135                 | 234                  |
| 2024 | Standard deviation | M3        | True      | 365            | 62             | 0                         | 132                 | 233                  |
| 2024 | Standard deviation | M5        | True      | 425            | 42             | 0                         | 180                 | 245                  |
| 2024 | Standard deviation | M10       | True      | 470            | 30             | 0                         | 220                 | 250                  |
| 2024 | Standard deviation | M15       | True      | 435            | 9              | 0                         | 180                 | 255                  |
| 2024 | Standard deviation | M30       | True      | 240            | 2              | 0                         | 240                 | 0                    |
| 2024 | Standard deviation | H1        | True      | 180            | 1              | 0                         | 180                 | 0                    |
| 2024 | Standard deviation | H4        | True      | 0              | 0              | 0                         | 0                   | 0                    |
| 2024 | Standard deviation | D1        | True      | 0              | 0              | 0                         | 0                   | 0                    |
| 2024 | FVG/IFVG reaction  | M1        | True      | 325            | 232            | 4                         | 154                 | 175                  |
| 2024 | FVG/IFVG reaction  | M3        | True      | 221            | 69             | 0                         | 75                  | 146                  |
| 2024 | FVG/IFVG reaction  | M5        | True      | 162            | 34             | 0                         | 95                  | 67                   |
| 2024 | FVG/IFVG reaction  | M10       | True      | 190            | 16             | 0                         | 20                  | 170                  |
| 2024 | FVG/IFVG reaction  | M15       | True      | 190            | 11             | 0                         | 55                  | 135                  |
| 2024 | FVG/IFVG reaction  | M30       | True      | 1              | 1              | 0                         | 0                   | 1                    |
| 2024 | FVG/IFVG reaction  | H1        | True      | 345            | 5              | 0                         | 0                   | 345                  |
| 2024 | FVG/IFVG reaction  | H4        | True      | 0              | 0              | 0                         | 0                   | 0                    |
| 2024 | FVG/IFVG reaction  | D1        | True      | 0              | 0              | 0                         | 0                   | 0                    |
| 2025 | PO3                | Any TF    | True      | 77544          | 14421          | 39241                     | 58253               | 58532                |
| 2025 | Order block        | M1        | True      | 11279          | 9359           | 0                         | 6068                | 5211                 |
| 2025 | Order block        | M3        | True      | 12128          | 3344           | 0                         | 6861                | 5267                 |
| 2025 | Order block        | M5        | True      | 12762          | 2095           | 0                         | 7192                | 5570                 |
| 2025 | Order block        | M10       | True      | 13741          | 1106           | 0                         | 7700                | 6041                 |
| 2025 | Order block        | M15       | True      | 14999          | 848            | 0                         | 8539                | 6460                 |
| 2025 | Order block        | M30       | True      | 13350          | 355            | 0                         | 9225                | 4125                 |
| 2025 | Order block        | H1        | True      | 13975          | 189            | 0                         | 8505                | 5470                 |
| 2025 | Order block        | H4        | True      | 9051           | 34             | 0                         | 6571                | 2480                 |
| 2025 | Order block        | D1        | True      | 13650          | 9              | 0                         | 10920               | 2730                 |
| 2025 | Standard deviation | M1        | True      | 49713          | 24194          | 0                         | 23432               | 26281                |
| 2025 | Standard deviation | M3        | True      | 50878          | 8236           | 0                         | 23564               | 27314                |
| 2025 | Standard deviation | M5        | True      | 51899          | 4970           | 0                         | 23467               | 28432                |
| 2025 | Standard deviation | M10       | True      | 51135          | 2469           | 0                         | 22181               | 28954                |
| 2025 | Standard deviation | M15       | True      | 44287          | 1310           | 0                         | 17810               | 26477                |
| 2025 | Standard deviation | M30       | True      | 41864          | 616            | 0                         | 16825               | 25039                |
| 2025 | Standard deviation | H1        | True      | 42112          | 295            | 0                         | 14970               | 27142                |
| 2025 | Standard deviation | H4        | True      | 31309          | 53             | 0                         | 10615               | 20694                |
| 2025 | Standard deviation | D1        | True      | 19110          | 7              | 0                         | 6825                | 12285                |
| 2025 | FVG/IFVG reaction  | M1        | True      | 38544          | 26533          | 428                       | 20181               | 18791                |
| 2025 | FVG/IFVG reaction  | M3        | True      | 28201          | 8761           | 0                         | 15014               | 13187                |
| 2025 | FVG/IFVG reaction  | M5        | True      | 27318          | 5151           | 0                         | 14657               | 12661                |
| 2025 | FVG/IFVG reaction  | M10       | True      | 26234          | 2555           | 0                         | 14944               | 11290                |
| 2025 | FVG/IFVG reaction  | M15       | True      | 26730          | 1706           | 0                         | 14433               | 12297                |
| 2025 | FVG/IFVG reaction  | M30       | True      | 28726          | 937            | 0                         | 15752               | 12974                |
| 2025 | FVG/IFVG reaction  | H1        | True      | 29350          | 462            | 0                         | 17119               | 12231                |
| 2025 | FVG/IFVG reaction  | H4        | True      | 31653          | 134            | 0                         | 21831               | 9822                 |
| 2025 | FVG/IFVG reaction  | D1        | True      | 14786          | 12             | 0                         | 12056               | 2730                 |
| 2026 | PO3                | Any TF    | True      | 59145          | 11172          | 30252                     | 45582               | 43815                |
| 2026 | Order block        | M1        | True      | 8935           | 7399           | 0                         | 4801                | 4134                 |
| 2026 | Order block        | M3        | True      | 9213           | 2562           | 0                         | 4867                | 4346                 |
| 2026 | Order block        | M5        | True      | 9700           | 1593           | 0                         | 5470                | 4230                 |
| 2026 | Order block        | M10       | True      | 9870           | 816            | 0                         | 5380                | 4490                 |
| 2026 | Order block        | M15       | True      | 10900          | 595            | 0                         | 5440                | 5460                 |
| 2026 | Order block        | M30       | True      | 11890          | 325            | 0                         | 6850                | 5040                 |
| 2026 | Order block        | H1        | True      | 12995          | 182            | 0                         | 7350                | 5645                 |
| 2026 | Order block        | H4        | True      | 7215           | 27             | 0                         | 2575                | 4640                 |
| 2026 | Order block        | D1        | True      | 1365           | 1              | 0                         | 1365                | 0                    |
| 2026 | Standard deviation | M1        | True      | 40338          | 19785          | 0                         | 19871               | 20467                |
| 2026 | Standard deviation | M3        | True      | 40750          | 6711           | 0                         | 19334               | 21416                |
| 2026 | Standard deviation | M5        | True      | 40940          | 4003           | 0                         | 18775               | 22165                |
| 2026 | Standard deviation | M10       | True      | 39590          | 1989           | 0                         | 18010               | 21580                |
| 2026 | Standard deviation | M15       | True      | 35965          | 1047           | 0                         | 15675               | 20290                |
| 2026 | Standard deviation | M30       | True      | 34110          | 514            | 0                         | 13780               | 20330                |
| 2026 | Standard deviation | H1        | True      | 35595          | 253            | 0                         | 13835               | 21760                |
| 2026 | Standard deviation | H4        | True      | 38010          | 62             | 0                         | 18960               | 19050                |
| 2026 | Standard deviation | D1        | True      | 16150          | 11             | 0                         | 3865                | 12285                |
| 2026 | FVG/IFVG reaction  | M1        | True      | 30215          | 20668          | 320                       | 15706               | 14829                |
| 2026 | FVG/IFVG reaction  | M3        | True      | 22554          | 6930           | 0                         | 11646               | 10908                |
| 2026 | FVG/IFVG reaction  | M5        | True      | 21430          | 4077           | 0                         | 11203               | 10227                |
| 2026 | FVG/IFVG reaction  | M10       | True      | 21212          | 2034           | 0                         | 11568               | 9644                 |
| 2026 | FVG/IFVG reaction  | M15       | True      | 20501          | 1328           | 0                         | 11924               | 8577                 |
| 2026 | FVG/IFVG reaction  | M30       | True      | 23074          | 729            | 0                         | 12758               | 10316                |
| 2026 | FVG/IFVG reaction  | H1        | True      | 23760          | 370            | 0                         | 13330               | 10430                |
| 2026 | FVG/IFVG reaction  | H4        | True      | 26349          | 105            | 0                         | 15206               | 11143                |
| 2026 | FVG/IFVG reaction  | D1        | True      | 15015          | 9              | 0                         | 6825                | 8190                 |

## How to read these counts

`active_m1_bars` counts M1 observations where that idea flag is active. An aligned higher-timeframe state may repeat across many M1 bars, so summing these values across timeframes double-counts correlated context.
`episode_starts` counts false-to-true transitions for one idea, timeframe, and direction. It is a context-episode count, not an executable trade count. The family totals in the annual table sum these episodes across source timeframes.
PO3 is counted from the cache's confirmed `entry_idea_po3_long/short` flags, which require an IFVG-confirmed distribution and a still-active gap. It is shown once as `Any TF` because this composite flag does not retain per-source-timeframe attribution. A manipulation/distribution state or liquidity sweep by itself is not counted as a PO3 entry candidate.
The FVG/IFVG family combines bullish and bearish FVG retests with inverse-FVG retests, then counts each direction's active union once per source timeframe.
`unique_bars_with_both_directions` counts rows where the union of the four reported idea families has both long and short context. It does not mean both sides were independently entry-ready. `cache_entry_idea_rows_with_both_directions` counts rows where the aggregate cache flags consumed by the entry state machine have both sides active; when a row otherwise supplies candidate evidence, the state machine treats those flags as conflicting evidence.
`both_sides_active_m1_bars` counts same-idea, same-timeframe bars with both directions active. `unique_bars_any_idea` counts each cached timestamp once even when ideas or timeframes overlap.
These are cached market-context signals before NY-session eligibility, policy actions, stop/target construction, account limits, and execution. They do not imply the same number of trades.
A signal source is marked unavailable when the cache has no corresponding source columns; its zero count must not be interpreted as evidence of no market opportunities.
