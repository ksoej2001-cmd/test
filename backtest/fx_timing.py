"""Monthly trend-following backtest on USD/JPY.

Spot returns only: interest-rate carry is not included, because no
interest-rate series for Japan was reachable from this environment.
Rules are chosen on the in-sample period only, then evaluated once on the
out-of-sample period. Run with --phase insample first, then --phase oos.

Data:
  data/usdjpy_daily.csv  Yen per US dollar, daily (FRED via
                         github.com/datasets/exchange-rates).
"""

import argparse

import pandas as pd

from sp500_timing import DATA, stats, table

IS_START, IS_END = "1971-03-01", "1999-12-31"
OOS_START = "2000-01-01"

COST = 0.0002  # per unit of position traded
LOOKBACKS = range(1, 13)
MODES = ("ls", "lo", "so")  # long/short, long USD or flat, long JPY or flat


def load():
    fx = pd.read_csv(DATA / "usdjpy_daily.csv", parse_dates=["Date"]).set_index("Date")["USDJPY"]
    price = fx.dropna().resample("ME").last()
    return pd.DataFrame({"price": price, "usd_ret": price.pct_change()}).dropna()


def run(df, mode, n):
    up = df["price"] > df["price"].shift(n)
    pos = {"ls": up * 2.0 - 1, "lo": up * 1.0, "so": up * 1.0 - 1}[mode]
    # Signal at month-end close, held over the next month.
    w = pos.where(df["price"].shift(n).notna()).shift(1)
    trades = w.diff().abs().fillna(0)
    ret = w * df["usd_ret"] - trades * COST
    return ret, w


def fx_stats(ret, w, start, end=None):
    out = stats(ret.loc[start:end], w.abs())
    w = w.loc[ret.loc[start:end].dropna().index]
    out["Trades/yr"] = w.diff().abs().sum() / (len(w) / 12)
    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--phase", choices=["insample", "oos"], required=True)
    ap.add_argument("--mode", choices=MODES)
    ap.add_argument("--n", type=int)
    a = ap.parse_args()
    df = load()

    if a.phase == "insample":
        rows = {"Hold USD": stats(df["usd_ret"].loc[IS_START:IS_END])}
        for mode in MODES:
            for n in LOOKBACKS:
                ret, w = run(df, mode, n)
                rows[f"{mode}{n}"] = fx_stats(ret, w, IS_START, IS_END)
        print(f"In-sample {IS_START[:7]} .. {IS_END[:7]}")
        print(table(rows))
        best = max((k for k in rows if k != "Hold USD"), key=lambda k: rows[k]["CAGR"])
        print(f"\nBest in-sample CAGR: {best}")
        return

    if a.mode is None or a.n is None:
        ap.error("--phase oos needs --mode and --n")
    ret, w = run(df, a.mode, a.n)
    rows = {
        "Hold USD": stats(df["usd_ret"].loc[OOS_START:]),
        f"{a.mode}{a.n}": fx_stats(ret, w, OOS_START),
    }
    print(f"Out-of-sample {OOS_START[:7]} .. {df.index[-1]:%Y-%m}")
    print(table(rows))


if __name__ == "__main__":
    main()
