# Daily and static maximum-loss floor boundaries

The user selected equality as permitted at both floors. With a $100,000
initial balance, daily equity exactly at $95,000 and static equity exactly at
$90,000 remain within limits; an equity value below either floor breaches.
Daily breaches permanently fail the full evaluation. The daily allowance
continues to use 5% of initial equity and the floor remains anchored to each
session's opening equity.

Payouts can only withdraw realized balance above the initial operating
balance. A loss cannot be paid out. The repeated-payout configuration still
requires its profit target and resets retained operating balance to $100,000.

The focused guardrail and payout-policy tests plus the daily full-evaluation
integration case pass on the existing GH200 allocation. The evidence covers
these boundary contracts; it does not establish all simulator/live parity or
broader lifecycle acceptance.

This equality selection applies to the daily floor and static maximum-loss
floor. The existing EOD/intraday ratcheted-floor touch behavior remains in
place below its initial-balance cap; equality is allowed when that floor is
capped at initial balance after payout.
