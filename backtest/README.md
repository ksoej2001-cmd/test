# S&P 500 timing backtest

Can a simple monthly timing rule beat buying and holding the S&P 500?

## Method

- Data: Shiller monthly S&P 500 with dividends, 1871 to 2026-09
  ([datasets/s-and-p-500](https://github.com/datasets/s-and-p-500)), and the US
  10-year Treasury yield ([datasets/bond-yields-us-10y](https://github.com/datasets/bond-yields-us-10y)).
- Candidate rules: hold stocks when the price is above its n-month moving
  average (`sma`), or above its price n months ago (`mom`), for n = 3 to 18.
  Otherwise hold a cash proxy that earns the 10-year yield.
- Costs: 0.1% per switch.
- Signals are applied with a two-month lag, because Shiller prices are monthly
  averages and a one-month lag would trade on the averaging artifact.
- The rule was chosen by highest CAGR on 1872–1949 only, then run once on
  1950–2026-09. The pass criterion, fixed in advance, was a higher CAGR than
  buy-and-hold out of sample.

## Result

In-sample (1872–1949), the best rule was `mom9`: 8.64% CAGR against 7.15%
for buy-and-hold.

Out-of-sample (1950–2026-09):

| | CAGR | Vol | Sharpe (rf=0) | Max drawdown | Time in market |
|---|---|---|---|---|---|
| Buy & hold | 11.70% | 12.02% | 0.99 | -49.0% | 100% |
| `mom9` | 10.90% | 9.19% | 1.18 | -26.0% | 74% |

The rule failed the pass criterion: it returned 0.8 points a year less than
buy-and-hold. It did cut the worst drawdown roughly in half and had a higher
risk-adjusted return.

## Caveats

- The cash proxy earns the 10-year yield and ignores bond price changes. A
  true T-bill rate was not available from this environment.
- Dividends after mid-2023 are missing in the source and are extrapolated from
  the last known dividend yield. The 10-year yield gap after 2023-09 is filled
  from the second dataset.
- No taxes. Monthly-average prices are not tradable prices.
- Momentum and moving-average timing rules were published and widely known
  well before 2026, so the out-of-sample period is not free of hindsight in
  the choice of rule families.

## Run

```
python3 sp500_timing.py --phase insample
python3 sp500_timing.py --phase oos --kind mom --n 9
```
