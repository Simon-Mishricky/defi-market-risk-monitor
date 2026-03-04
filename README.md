# DeFi Liquidation Risk Simulator

A theory-driven simulator that stress-tests DeFi lending protocols under collateral price shocks, combining agent-based cascade simulation with the equilibrium flash crash model of **Mishricky (2025)**.

---

## What is this?

DeFi lending protocols like Aave let users borrow against crypto collateral. If the collateral price falls enough, the protocol automatically liquidates the position — a bot repays the debt and seizes the collateral at a discount.

The danger is that liquidations can feed on themselves. Imagine ETH drops 30%. Thousands of positions are liquidated simultaneously. The liquidation bots sell the seized ETH to repay stablecoin debt, pushing ETH down further. That triggers more liquidations. This self-reinforcing loop is called a **liquidation cascade**, and it is what destroyed hundreds of millions of dollars in protocols like Venus and Compound during the May 2021 and November 2022 crashes.

This simulator models exactly that process on a synthetic Aave V3-equivalent pool ($1.8B collateral, $762M debt, 1,000 borrower positions). You choose a price drop, hit run, and watch the cascade unfold round by round.

---

## What makes it different?

Most liquidation simulators stop at counting how many positions get liquidated and how much bad debt accumulates. That is useful, but it misses a deeper question: **is there enough liquidity and competitive market activity to actually execute these liquidations without the price gapping?**

If liquidation bots cannot profitably participate — because gas costs are too high, or because stablecoin liquidity has dried up — no one posts competitive quotes. The market gaps. This is a flash crash.

This simulator tracks the **theoretical flash crash probability F** at each round of the cascade, derived from the equilibrium model in Mishricky (2025). F is calibrated from three observable quantities:

- **Gas cost per liquidation** (κ in the model) — high gas makes liquidation unprofitable, bots exit
- **Stablecoin liquidity depth as a fraction of total debt** (φᵐ) — as liquidations consume liquidity, this falls
- **Collateral volatility** (Γ) — wider price swings widen the book but also increase execution risk

As the cascade progresses, liquidity drains and F rises. The dashboard shows this transition in real time.

---

## The conservation law

The central theoretical result is a **conservation law** (Mishricky 2025, Footnote 28):

```
MSE · F = (κ / φᵐ)²
```

This says that the product of price dispersion (MSE) and flash crash probability (F) is determined entirely by the ratio of posting costs to liquidity. The practical implication: **a protocol can show low F while generating massive bad debt**, because the bad debt raises MSE even as F appears controlled. The 40% and 50% drop scenarios in this simulator reproduce exactly that pattern — $48M and $174M in bad debt respectively, both with F remaining in the STABLE range. Standard risk monitors would not flag either scenario as critical.

---

## Theoretical framework

The model implements the equilibrium from Mishricky (2025), which combines the Burdett-Judd (1983) price posting framework with the Lagos-Wright (2005) monetary model:

| Theoretical parameter | DeFi observable |
|---|---|
| κ (quote posting cost) | Gas cost per liquidation (USD) |
| φᵐ (real value of money) | Stablecoin liquidity depth / total protocol debt |
| Γ (book width) | Daily volatility of collateral asset |

**Core results implemented:**

- Flash crash probability: `F = e^(-θ)` where `θ = ln(φᵐ Γ / κ)`
- Proposition 1: Equilibrium bid/ask distributions A(p) and B(p)
- Proposition 11: F is increasing in κ and decreasing in φᵐ
- Proposition 12: Speculative premium
- Conservation law: `MSE · F = (κ / φᵐ)²`

**Interpreting F:** F is a *per-cycle* probability — the chance that no competitive quote is posted in a single auction round. Small per-cycle values compound rapidly: at 1,000 quote cycles per hour, F = 0.0005 gives a daily flash crash probability of `1 - (1 - 0.0005)^24000 ≈ 100%`.

Market status thresholds calibrated to a $1.8B Aave V3-equivalent pool:

| Status | F threshold | What it means |
|---|---|---|
| STABLE | F < 0.00005 | Competitive liquidation market, low flash crash risk |
| ELEVATED RISK | 0.00005 ≤ F < 0.00050 | Liquidity thinning, market quality degrading |
| CRITICAL | F ≥ 0.00050 | Near-certain daily flash crash, protocol solvency at risk |

---

## Crisis scenario presets

| Preset | Price drop | Liquidity | Gas | What it models |
|---|---|---|---|---|
| Normal market | 30% | 40% | $80 | Baseline conditions. Starts STABLE, deteriorates to ELEVATED RISK as cascade drains liquidity — this is the hidden fragility the model detects. |
| Liquidity crisis | 30% | 3% | $80 | Capital has fled the protocol before the shock hits. φᵐ is already near zero, so the market is fragile from round one. |
| Gas spike | 30% | 40% | $450 | κ shock. Gas cost raised to $450, raising F and degrading market quality. Large positions remain profitable to liquidate — the scenario demonstrates how κ elevates flash crash risk even without generating meaningful bad debt. |
| Combined shock | 45% | 5% | $400 | Both liquidity and gas fail simultaneously. Analogue of March 2020 (COVID) or November 2022 (FTX collapse). |

---

## Project structure

```
defi-liquidation-sim/
├── fetch_aave.py          # Synthetic pool data calibrated to Aave V3 Ethereum
├── agents.py              # BorrowerAgent class with health factor calculation
├── simulate.py            # Cascade loop with bad debt accounting and theory scoring
├── theory.py              # BurdettJuddDeFi class implementing Mishricky (2025)
├── dashboard.py           # Plotly Dash interactive dashboard
├── test_theory.py         # Gas/liquidity stress tests
├── test_distributions.py  # Bid/ask distribution plots under stress
└── test_speculation.py    # Speculative premium analysis
```

---

## Getting started

**Requirements:** Python 3.9+

```bash
pip install dash plotly pandas numpy scipy
```

### Run the dashboard

```bash
python dashboard.py
```

Open [http://127.0.0.1:8050](http://127.0.0.1:8050) in your browser.

### Run the simulation directly

```bash
python simulate.py
```

Runs five benchmark scenarios (10%–50% price drops) and prints round-by-round cascade results with theoretical scores.

### Run theory tests

```bash
python test_theory.py        # Stress test F across gas/liquidity parameter space
python test_distributions.py # Plot bid/ask distributions under each crisis preset
python test_speculation.py   # Analyse speculative premium (Proposition 12)
```

---

## Dashboard features

- **4 crisis scenario presets** with one-click switching
- **Interactive sliders** for price drop (5–60%), liquidity (1–80%), and gas cost ($20–500)
- **10 summary statistics** including bad debt, cascade rounds, initial/final F, and market status
- **4 charts:** liquidation cascade by round, θ and F evolution, equilibrium bid/ask distributions, full stress test

---

## Limitations and extensions

The model correctly predicts the qualitative structure of cascade risk and identifies the liquidity threshold at which protocol solvency deteriorates. Full quantitative validation of F against empirical liquidation gap frequency from historical on-chain data (March 2020, November 2022) requires time-series data not yet integrated.

Natural extensions:
- Multi-asset collateral pools
- Cross-protocol contagion (Aave ↔ Compound ↔ Morpho)
- Endogenous gas pricing during congestion
- Live data feed via Aave subgraph or on-chain RPC

---

## Reference

Mishricky, S. (2025). *Asset Price Dispersion, Monetary Policy and Macroprudential Regulation*. Working paper, Australian National University.
