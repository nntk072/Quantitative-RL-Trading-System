# Trading and simulation

## Overview

Broker-neutral account, order, position, risk, decision, and execution contracts meet in the simulation environment. The environment defines the ordering of market advancement, protection checks, action validation, fills, accounting, and reward.

## Concepts

Risk budgets determine permitted exposure; order geometry fixes entry, stop, and target before sizing. Historical fills are modelled outcomes and do not guarantee live execution.

See [Trading and risk](../learn/tutorials/03_trading_and_risk.ipynb), [one environment step](../learn/tutorials/04_environment.ipynb), [risk and account limits](../concepts/risk_and_account_limits), [trade setups](../concepts/trade_setups), and [execution and costs](../concepts/execution_and_costs).

## Reference

Start with the [Trading API](../api/domains/trading), [public contracts](../reference/public_contracts), [action schemas](../reference/action_schemas), and [risk and execution reference](../reference/risk_and_execution).
