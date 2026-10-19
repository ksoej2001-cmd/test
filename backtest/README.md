# Timing backtests

Can a simple monthly rule beat buying and holding? Three tests: timing the
S&P 500 (`sp500_timing.py`), timing USD/JPY (`fx_timing.py`), and picking
stocks within the S&P 500 (`stock_selection.py`).

## S&P 500

### Method

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

### Result

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

### Caveats

- The cash proxy earns the 10-year yield and ignores bond price changes. A
  true T-bill rate was not available from this environment.
- Dividends after mid-2023 are missing in the source and are extrapolated from
  the last known dividend yield. The 10-year yield gap after 2023-09 is filled
  from the second dataset.
- No taxes. Monthly-average prices are not tradable prices.
- Momentum and moving-average timing rules were published and widely known
  well before 2026, so the out-of-sample period is not free of hindsight in
  the choice of rule families.

## USD/JPY

### Method

- Data: yen per US dollar, daily, 1971 to 2026-10 (FRED, via
  [datasets/exchange-rates](https://github.com/datasets/exchange-rates)),
  sampled at month-end.
- Candidate rules: compare the month-end rate with the rate n months earlier,
  n = 1 to 12. If the dollar has risen, hold the dollar; otherwise either hold
  the yen (`ls`, long/short), stay flat (`lo`), or the mirror image (`so`).
  No leverage.
- Costs: 0.02% per unit of position traded. Signals are formed at the
  month-end close and held over the next month.
- The rule was chosen by highest CAGR on 1971–1999 only, then run once on
  2000–2026-10. The pass criterion, fixed in advance, was a positive CAGR out
  of sample that also beats holding the dollar.

### Result

In-sample (1971–1999), holding the dollar lost 4.25% a year as the yen rose
from about 358 to about 102. The best rule was `ls4`: +5.25% a year.

Out-of-sample (2000–2026-10):

| | CAGR | Vol | Sharpe (rf=0) | Max drawdown | Trades/yr |
|---|---|---|---|---|---|
| Hold USD | 1.65% | 9.51% | 0.22 | -43.1% | 0 |
| `ls4` | 0.52% | 9.52% | 0.10 | -27.4% | 5.37 |

The rule failed the pass criterion. Its return stayed positive but fell short
of simply holding the dollar.

### Caveats

- Spot returns only. Interest-rate carry is excluded because no Japanese rate
  series was reachable from this environment. US rates were above Japanese
  rates for most of 2000–2026, so including carry would likely favor holding
  the dollar and hurt `ls4`, which held the yen part of the time.
- FRED rates are noon buying rates in New York, not tradable quotes.

## Stock selection within the S&P 500

### Method

- Data: 5-minute bars for S&P 500 members, 2020–2024, and daily index
  membership, from the [y-not-finance data release](https://github.com/PIMPOON/DATA/releases/tag/Y-Not-Finance).
  The bars are unadjusted and contain stray prints. `prepare_stocks.py`
  cleans them into month-end prices; see its docstring and
  `data/stocks_cleaning.csv` for every split found and ticker dropped
  (AIV, KLG, PHIN). Prices exclude dividends.
- Each month-end, among the stocks in the index that day, hold the top 50 by
  one of: return from n months ago to one month ago (`mom3`, `mom6`,
  `mom9`, `mom12`), or the worst return last month (`rev1`). Equal weights,
  rebalanced monthly, 0.1% cost per unit of turnover. A stock with no price
  the next month (delisted) earns 0 for that month.
- Benchmark: every index member, equally weighted, built from the same data.
- The rule was chosen by highest CAGR over holding months 2021-02 to 2022-12,
  then run once on 2023–2024. The pass criterion, fixed in advance, was a
  higher CAGR than the benchmark out of sample.

### Result

In-sample, `mom6` was best: 8.81% a year against 5.67% for the benchmark.
Picking last month's losers (`rev1`) lost money.

Out-of-sample (holding months 2023-01 to 2024-12):

| | CAGR | Vol | Sharpe (rf=0) | Max drawdown |
|---|---|---|---|---|
| Equal weight, all members | 11.59% | 15.65% | 0.78 | -12.0% |
| `mom6` | 14.39% | 15.15% | 0.96 | -12.1% |

`mom6` passed the pass criterion. The edge is not statistically meaningful:
the mean monthly difference was +0.20% with a t-statistic of 0.42 over 24
months.

The S&P 500 index itself, which is weighted by market value, rose about 24%
a year in price over the same two years (Shiller monthly averages, December
2022 to December 2024). Both equal-weight portfolios trailed it by a wide
margin, because a handful of the largest companies led the market.

### Caveats

- Only five years of data; the out-of-sample period is 24 months.
- Split detection is heuristic. IR shows a ratio-4 "split" on 2020-03-03,
  which is the ticker passing from the old Ingersoll-Rand to Gardner Denver;
  it falls before any rule's first signal.
- Spin-offs are not adjusted and show up as price drops.
- No dividends. Delisted stocks are assumed sold at their last price, which
  is generous for failures such as First Republic and SVB.

## Run

```
python3 sp500_timing.py --phase insample
python3 sp500_timing.py --phase oos --kind mom --n 9
python3 fx_timing.py --phase insample
python3 fx_timing.py --phase oos --mode ls --n 4
python3 prepare_stocks.py --src <dir with the two parquet files>
python3 stock_selection.py --phase insample
python3 stock_selection.py --phase oos --rule mom6
```
