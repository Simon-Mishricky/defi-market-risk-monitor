import traceback
import numpy as np
import pandas as pd
from agents import BorrowerAgent
from fetch_aave import generate_aave_positions
from theory import calibrate_from_positions


def run_cascade(price_drop_pct, n_positions=1000, price_impact_factor=0.000000001, gas_usd=80.0, initial_liquidity_pct=0.40, daily_volatility=0.05):

    positions = generate_aave_positions(n=n_positions)
    agents = [
        BorrowerAgent(i, row.collateral_usd, row.debt_usd)
        for i, row in positions.iterrows()
    ]

    total_debt_initial = positions['debt_usd'].sum()
    available_liquidity = total_debt_initial * initial_liquidity_pct

    initial_price_ratio = 1 - price_drop_pct
    for agent in agents:
        agent.apply_price_shock(initial_price_ratio)

    current_price = initial_price_ratio
    results = []

    while True:
        liquidatable = [a for a in agents if a.is_liquidatable()]

        if not liquidatable:
            break

        round_num = len(results) + 1
        round_liquidation_volume = 0
        round_bad_debt = 0

        for agent in liquidatable:
            debt_to_repay = agent.debt * 0.5
            collateral_seized = debt_to_repay * (1 + agent.liq_bonus)

            # --- Check 1: Is liquidation profitable for the bot? ---
            # Bot earns liq_bonus * collateral_seized but pays gas_usd.
            # If gas exceeds the bonus, no rational bot will liquidate.
            liquidation_profit = agent.liq_bonus * min(collateral_seized, agent.collateral)
            if gas_usd > liquidation_profit:
                # Unprofitable — position stays underwater, full debt is bad debt
                round_bad_debt += max(agent.debt - agent.collateral, 0)
                agent.debt = 0
                agent.collateral = 0
                agent.liquidated = True
                continue

            # --- Check 2: Is there enough stablecoin liquidity to fund repayment? ---
            # Bot needs debt_to_repay in stablecoins. If liquidity is insufficient,
            # only a partial liquidation occurs; the remainder is bad debt.
            if available_liquidity < debt_to_repay:
                actual_repay = available_liquidity
                actual_seized = min(actual_repay * (1 + agent.liq_bonus), agent.collateral)
                shortfall = agent.debt - actual_repay - max(agent.collateral - actual_seized, 0)
                round_bad_debt += max(shortfall, 0)
                round_liquidation_volume += actual_seized
                available_liquidity = 0
                agent.debt = 0
                agent.collateral = 0
                agent.liquidated = True
                continue

            # --- Standard liquidation ---
            if collateral_seized > agent.collateral:
                collateral_seized = agent.collateral
                round_bad_debt += max(agent.debt - agent.collateral, 0)
                agent.debt = 0
                agent.collateral = 0
                agent.liquidated = True
                continue

            agent.debt -= debt_to_repay
            agent.collateral -= collateral_seized
            agent.liquidated = True
            round_liquidation_volume += collateral_seized
            available_liquidity -= debt_to_repay

        available_liquidity = max(
            available_liquidity,
            total_debt_initial * 0.05  # floor at 5% of initial debt
        )

        additional_price_drop = price_impact_factor * round_liquidation_volume
        current_price *= (1 - additional_price_drop)
        for agent in agents:
            if not agent.liquidated:
                agent.apply_price_shock(1 - additional_price_drop)

        surviving = [a for a in agents if not a.liquidated]
        surviving_debt = sum(a.debt for a in surviving)
        surviving_collateral = sum(a.collateral for a in surviving)

        if surviving_debt > 0 and len(surviving) > 0:
            surviving_df = pd.DataFrame({
                'collateral_usd': [a.collateral for a in surviving],
                'debt_usd':       [a.debt for a in surviving],
                'health_factor':  [a.health_factor for a in surviving]
            })

            try:
                model = calibrate_from_positions(
                    surviving_df,
                    gas_usd=gas_usd,
                    stablecoin_depth_usd=available_liquidity,
                    daily_volatility=daily_volatility
                )
                theta = round(model.theta, 4)
                F = round(model.flash_crash_prob, 6)
                real_spread = round(model.real_spread, 6)
                cv_bid = round(model.cv_bid, 6)
                status = model.summary()['market status']
            except ValueError:
                theta = 0
                F = 1.0
                real_spread = float('inf')
                cv_bid = float('inf')
                status = "COLLAPSE"
        else:
            theta = 0
            F = 1.0
            real_spread = float('inf')
            cv_bid = float('inf')
            status = "COLLAPSE"

        results.append({
            "round":                   round_num,
            "price":                   round(current_price, 4),
            "liquidations":            len(liquidatable),
            "liquidation_vol_usd":     round(round_liquidation_volume, 0),
            "bad_debt_usd":            round(round_bad_debt, 0),
            "available_liquidity_usd": round(available_liquidity, 0),
            "surviving_positions":     len(surviving),
            "pool_collateral_ratio":   round(surviving_collateral / max(surviving_debt, 1), 3),
            "theta":                   theta,
            "F (crash prob)":          F,
            "real_spread":             real_spread,
            "cv_bid":                  cv_bid,
            "market_status":           status
        })

    return pd.DataFrame(results), agents


# --- Run and display ---
pd.set_option('display.max_columns', None)
pd.set_option('display.width', 120)

scenarios = [0.10, 0.20, 0.30, 0.40, 0.50]

for drop in scenarios:
    print("=" * 80)
    print(f"SCENARIO: {int(drop*100)}% PRICE DROP — Mishricky (2025) Framework")
    print("=" * 80)
    try:
        results, agents = run_cascade(price_drop_pct=drop)
        print(results.to_string(index=False))

        total_liquidated = sum(1 for a in agents if a.liquidated)
        total_bad_debt = results['bad_debt_usd'].sum()

        print(f"\nTotal positions liquidated:  {total_liquidated} / 1000")
        print(f"Total bad debt generated:    ${total_bad_debt:,.0f}")
        print(f"Cascade rounds:              {len(results)}")
        print(f"Final theoretical F:         {results['F (crash prob)'].iloc[-1]}")
        print(f"Final market status:         {results['market_status'].iloc[-1]}")
        print()
    except Exception as e:
        traceback.print_exc()