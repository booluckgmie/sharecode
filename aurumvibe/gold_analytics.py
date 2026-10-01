"""Extra analytics charts for the AurumVibe daily report.

Two dark-theme PNGs, built from the same DataFrame as the main chart
(columns: Price RM/g, USD_Price USD/oz, Rate USD/MYR; date index):

  gold_drivers.png - what moved the RM price (gold in USD vs the ringgit)
  gold_risk.png    - risk and timing (drawdown, return spread, volatility, range)

Layout uses constrained_layout, one title per panel, and end-of-line labels
that are spread apart explicitly, so text and marks do not collide.
"""
import numpy as np
import pandas as pd
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import matplotlib.dates as mdates

SURFACE = "#1a1a19"
INK     = "#ffffff"
INK_2   = "#c3c2b7"
MUTED   = "#8a8980"
GRID    = "#33322f"
BLUE    = "#3987e5"   # gold in USD
ORANGE  = "#d95926"   # USD/MYR
AQUA    = "#199e70"   # RM/g
RED     = "#e66767"

DRIVERS_PNG = "gold_drivers.png"
RISK_PNG    = "gold_risk.png"


def _style(ax, title):
    ax.set_facecolor(SURFACE)
    ax.set_title(title, color=INK, fontsize=11, loc="left", pad=8)
    ax.tick_params(colors=MUTED, labelsize=8, length=0)
    ax.grid(True, color=GRID, linewidth=0.6, alpha=0.8)
    ax.set_axisbelow(True)
    for s in ax.spines.values():
        s.set_visible(False)


def _date_axis(ax):
    ax.xaxis.set_major_locator(mdates.AutoDateLocator(minticks=3, maxticks=6))
    ax.xaxis.set_major_formatter(mdates.DateFormatter("%d %b"))


def _spread(ys, min_gap):
    """Nudge label y-positions apart so none are closer than min_gap."""
    order = np.argsort(ys)
    out = np.array(ys, dtype=float)
    for a, b in zip(order[:-1], order[1:]):
        if out[b] - out[a] < min_gap:
            out[b] = out[a] + min_gap
    shift = (np.mean(ys) - np.mean(out))
    return out + shift


def _legend(ax, **kw):
    leg = ax.legend(frameon=False, fontsize=8, labelcolor=INK_2, **kw)
    return leg


def _new_fig(figsize, rows, cols, **gs):
    fig, axes = plt.subplots(rows, cols, figsize=figsize,
                             constrained_layout=True, **gs)
    fig.patch.set_facecolor(SURFACE)
    fig.get_layout_engine().set(w_pad=0.25, h_pad=0.25, wspace=0.08, hspace=0.1)
    return fig, axes


def _footer(fig, text):
    fig.text(0.01, -0.005, text, color=MUTED, fontsize=7.5, ha="left", va="top")


# ---------------------------------------------------------------------------
# Image 1 - drivers
# ---------------------------------------------------------------------------
def create_drivers_chart(df, path=DRIVERS_PNG):
    d = df[["Price", "USD_Price", "Rate"]].dropna().copy()
    base = d.iloc[-90:] if len(d) > 90 else d
    idx = base / base.iloc[0] * 100

    fig, (ax1, ax2) = _new_fig((11, 8.5), 2, 1,
                               gridspec_kw={"height_ratios": [3, 2]})

    # Panel 1: indexed lines (one axis, common base 100)
    _style(ax1, f"Indexed to 100 at {base.index[0]:%d %b} - gold in USD vs ringgit vs RM/g")
    series = [("RM per gram", idx["Price"], AQUA, 2.4),
              ("Gold USD/oz", idx["USD_Price"], BLUE, 1.6),
              ("USD/MYR", idx["Rate"], ORANGE, 1.6)]
    for name, s, c, lw in series:
        ax1.plot(s.index, s.values, color=c, linewidth=lw, label=name)
    ax1.axhline(100, color=MUTED, linewidth=0.8, linestyle=":")
    lo, hi = idx.min().min(), idx.max().max()
    ax1.set_ylim(lo - (hi - lo) * 0.06, hi + (hi - lo) * 0.06)
    ax1.set_xlim(base.index[0], base.index[-1] + (base.index[-1] - base.index[0]) * 0.16)
    ends = [s.iloc[-1] for _, s, _, _ in series]
    ys = _spread(ends, (hi - lo) * 0.07)
    for (name, s, c, _), y in zip(series, ys):
        ax1.annotate(f"{s.iloc[-1]:.1f}", xy=(s.index[-1], s.iloc[-1]),
                     xytext=(s.index[-1] + (base.index[-1] - base.index[0]) * 0.02, y),
                     color=INK, fontsize=9, va="center",
                     arrowprops=dict(arrowstyle="-", color=c, lw=0.8))
    _legend(ax1, loc="upper left", ncol=3)
    _date_axis(ax1)

    # Panel 2: attribution of the daily RM move (log returns add exactly)
    n = 30
    r = np.log(d).diff().dropna().iloc[-n:] * 100
    gold_c, fx_c = r["USD_Price"], r["Rate"]
    _style(ax2, f"What drove each day's RM/g move (last {len(r)} trading days, % points)")
    x = np.arange(len(r))
    ax2.bar(x, gold_c, width=0.7, color=BLUE, label="Gold in USD",
            edgecolor=SURFACE, linewidth=1.2)
    ax2.bar(x, fx_c, width=0.7, bottom=gold_c.where(np.sign(gold_c) == np.sign(fx_c), 0),
            color=ORANGE, label="USD/MYR (ringgit)", edgecolor=SURFACE, linewidth=1.2)
    ax2.plot(x, gold_c + fx_c, color=INK, linewidth=0, marker="o", markersize=4,
             markeredgecolor=SURFACE, markeredgewidth=1.0, label="Net RM/g move")
    ax2.axhline(0, color=MUTED, linewidth=0.8)
    ticks = np.linspace(0, len(r) - 1, 6).astype(int)
    ax2.set_xticks(ticks)
    ax2.set_xticklabels([f"{r.index[i]:%d %b}" for i in ticks])
    pad = max(abs((gold_c + fx_c).max()), abs((gold_c + fx_c).min()), 1) * 0.35
    ymax = max((gold_c.clip(lower=0) + fx_c.clip(lower=0)).max(), 0)
    ymin = min((gold_c.clip(upper=0) + fx_c.clip(upper=0)).min(), 0)
    ax2.set_ylim(ymin - pad, ymax + pad * 2.2)
    _legend(ax2, loc="upper left", ncol=3)

    fx_share = (fx_c.abs().sum() / (fx_c.abs().sum() + gold_c.abs().sum())) * 100
    fig.suptitle("AurumVibe Drivers", color=INK, fontsize=13, x=0.01, ha="left")
    _footer(fig, f"Over these {len(r)} days the ringgit explains {fx_share:.0f}% of absolute RM/g movement; "
                 f"the rest is gold itself.   Data: Yahoo Finance GC=F x MYR=X")
    fig.savefig(path, dpi=140, facecolor=SURFACE, bbox_inches="tight")
    plt.close(fig)
    return path


# ---------------------------------------------------------------------------
# Image 2 - risk & timing
# ---------------------------------------------------------------------------
def create_risk_chart(df, path=RISK_PNG):
    p = df["Price"]
    ret = p.pct_change().dropna() * 100
    dd = (p / p.cummax() - 1) * 100
    vol = ret.rolling(10).std() * np.sqrt(252)

    fig, axes = _new_fig((11, 8.5), 2, 2)
    (ax1, ax2), (ax3, ax4) = axes

    # 1. Drawdown from running high
    _style(ax1, "Drawdown from running high (%)")
    ax1.fill_between(dd.index, dd.values, 0, color=RED, alpha=0.30, linewidth=0)
    ax1.plot(dd.index, dd.values, color=RED, linewidth=1.6)
    ax1.scatter([dd.index[-1]], [dd.iloc[-1]], color=RED, s=40, zorder=5,
                edgecolor=SURFACE, linewidth=1.5)
    ax1.set_ylim(dd.min() * 1.15, 1)
    ax1.set_title(f"Drawdown from running high (%) - now {dd.iloc[-1]:.1f}%, "
                  f"worst {dd.min():.1f}%", color=INK, fontsize=11, loc="left", pad=8)
    _date_axis(ax1)

    # 2. Distribution of daily moves
    _style(ax2, "Daily % moves - how unusual is today?")
    bins = np.linspace(min(ret.min(), -0.1), max(ret.max(), 0.1), 21)
    ax2.hist(ret, bins=bins, color=BLUE, alpha=0.9, edgecolor=SURFACE, linewidth=1.2)
    today = ret.iloc[-1]
    ax2.axvline(today, color=INK, linewidth=1.6)
    pct_rank = (ret < today).mean() * 100
    ax2.set_ylim(0, ax2.get_ylim()[1] * 1.18)
    ax2.annotate(f"today {today:+.2f}%\n(rank {pct_rank:.0f}th pct)",
                 xy=(today, ax2.get_ylim()[1] * 0.97), color=INK, fontsize=8.5, va="top",
                 ha="left" if today < ret.mean() + ret.std() else "right",
                 xytext=(6 if today < ret.mean() + ret.std() else -6, 0),
                 textcoords="offset points")
    ax2.set_xlabel("daily change (%)", color=MUTED, fontsize=8)
    ax2.set_ylabel("days", color=MUTED, fontsize=8)

    # 3. Rolling volatility
    _style(ax3, f"10-day volatility (annualised %) - now {vol.dropna().iloc[-1]:.0f}%, "
                    f"median {vol.dropna().median():.0f}% (dotted)")
    v = vol.dropna()
    ax3.plot(v.index, v.values, color=BLUE, linewidth=1.8)
    ax3.axhline(v.median(), color=MUTED, linewidth=0.9, linestyle=":")
    ax3.scatter([v.index[-1]], [v.iloc[-1]], color=BLUE, s=40, zorder=5,
                edgecolor=SURFACE, linewidth=1.5)
    ax3.set_ylim(0, v.max() * 1.25)
    _date_axis(ax3)

    # 4. Where is price inside each lookback range?
    _style(ax4, "Where price sits in its range (0% = low, 100% = high)")
    ax4.grid(False)
    ax4.grid(True, axis="x", color=GRID, linewidth=0.6)
    rows = []
    for label, n in [("7 days", 7), ("30 days", 30), ("90 days", 90), ("All data", len(p))]:
        w = p.iloc[-n:]
        lo, hi = w.min(), w.max()
        rows.append((label, (p.iloc[-1] - lo) / (hi - lo) * 100 if hi > lo else 50, lo, hi))
    ys = np.arange(len(rows))[::-1]
    for y, (label, pos, lo, hi) in zip(ys, rows):
        ax4.barh(y, 100, height=0.34, color=GRID)
        ax4.barh(y, pos, height=0.34, color=BLUE)
        ax4.scatter([pos], [y], color=INK, s=46, zorder=5, edgecolor=SURFACE, linewidth=1.5)
        ax4.text(0, y + 0.34, f"{label}   RM {lo:.0f} - {hi:.0f}", color=INK_2,
                 fontsize=8, va="bottom", ha="left")
        ax4.text(100, y + 0.34, f"{pos:.0f}%", color=INK, fontsize=8.5,
                 va="bottom", ha="right")
    ax4.set_xlim(0, 100)
    ax4.set_ylim(-0.6, len(rows) - 0.1)
    ax4.set_yticks([])
    ax4.set_xticks([0, 25, 50, 75, 100])
    ax4.set_xticklabels(["0%", "25%", "50%", "75%", "100%"])

    fig.suptitle("AurumVibe Risk & Timing", color=INK, fontsize=13, x=0.01, ha="left")
    _footer(fig, f"Price RM {p.iloc[-1]:.2f}/g on {p.index[-1]:%d %b %Y}.   "
                 f"Data: Yahoo Finance GC=F x MYR=X")
    fig.savefig(path, dpi=140, facecolor=SURFACE, bbox_inches="tight")
    plt.close(fig)
    return path


def create_analytics_charts(df):
    return [create_drivers_chart(df), create_risk_chart(df)]
