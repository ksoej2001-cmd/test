"""Monthly stock-selection backtest within the S&P 500, 2020-2024.

Each month-end, rank the index members and hold the top 50 equally weighted
for the next month. Compared against holding every member equally weighted.
Rules are chosen on the in-sample period only, then evaluated once on the
out-of-sample period. Run with --phase insample first, then --phase oos.

Data comes from prepare_stocks.py. Prices exclude dividends, for the rules
and the benchmark alike.
"""

import argparse

import numpy as np
import pandas as pd

from sp500_timing import DATA, stats, table

IS_START, IS_END = "2021-02-01", "2022-12-31"
OOS_START = "2023-01-01"

TOP = 50
COST = 0.001  # per unit of one-way turnover
RULES = ["mom3", "mom6", "mom9", "mom12", "rev1"]


def load():
    px = pd.read_csv(DATA / "stocks_monthly.csv", index_col=0, parse_dates=True)
    m = pd.read_csv(DATA / "sp500_members.csv", parse_dates=["date"])
    members = m.assign(v=True).pivot(index="date", columns="ticker", values="v")
    members = members.reindex(index=px.index, columns=px.columns).fillna(False).astype(bool)
    return px, members


def scores(px, rule):
    if rule.startswith("mom"):
        n = int(rule[3:])
        # Return from n months ago to one month ago; skip the latest month.
        return px.shift(1) / px.shift(n) - 1
    if rule == "rev1":
        return -(px / px.shift(1) - 1)
    raise ValueError(rule)


def weights(px, members, rule):
    sc = scores(px, rule).where(members & px.notna())
    rank = sc.rank(axis=1, ascending=False, method="first")
    w = (rank <= TOP).astype(float)
    return w.div(w.sum(axis=1), axis=0).where(sc.notna().sum(axis=1) >= TOP, np.nan)


def equal_weights(px, members):
    w = (members & px.notna()).astype(float)
    return w.div(w.sum(axis=1), axis=0)


def backtest(px, w):
    # Holding month return; a stock with no price next month (delisted) earns 0.
    nxt = (px.shift(-1) / px - 1).fillna(0)
    gross = (w * nxt).sum(axis=1, min_count=1).shift(1)
    drift = w * (1 + nxt)
    drift = drift.div(drift.sum(axis=1), axis=0).shift(1)
    turnover = (w.fillna(0) - drift.fillna(0)).abs().sum(axis=1)
    return (gross - turnover * COST).dropna()


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--phase", choices=["insample", "oos"], required=True)
    ap.add_argument("--rule", choices=RULES)
    a = ap.parse_args()
    px, members = load()
    bench = backtest(px, equal_weights(px, members))

    if a.phase == "insample":
        rows = {"EqualAll": stats(bench.loc[IS_START:IS_END])}
        for rule in RULES:
            rows[rule] = stats(backtest(px, weights(px, members, rule)).loc[IS_START:IS_END])
        print(f"In-sample {IS_START[:7]} .. {IS_END[:7]} (holding months)")
        print(table(rows))
        best = max(RULES, key=lambda k: rows[k]["CAGR"])
        print(f"\nBest in-sample CAGR: {best}")
        return

    if a.rule is None:
        ap.error("--phase oos needs --rule")
    ret = backtest(px, weights(px, members, a.rule))
    rows = {"EqualAll": stats(bench.loc[OOS_START:]), a.rule: stats(ret.loc[OOS_START:])}
    print(f"Out-of-sample {OOS_START[:7]} .. {ret.index[-1]:%Y-%m} (holding months)")
    print(table(rows))


if __name__ == "__main__":
    main()
