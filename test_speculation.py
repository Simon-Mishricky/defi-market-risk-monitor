import numpy as np
from fetch_aave import generate_aave_positions
from theory import calibrate_from_positions

positions = generate_aave_positions(n=1000)
total_debt = positions['debt_usd'].sum()
baseline_depth = total_debt * 0.40  # baseline liquidity

print("=== Speculative Premium — Proposition 12 ===\n")

# Proposition 12(ii): P increases with kappa
print("Gas stress (kappa up -> P up):")
print(f"{'Gas Cost':<12} {'theta':<10} {'F':<10} {'phi_m':<8} {'Fund. Value':<14} {'Spec. Premium'}")
print("-" * 70)
for gas in [20, 80, 300, 1000, 2000]:
    try:
        m = calibrate_from_positions(positions, gas, baseline_depth, 0.05)
        print(f"  ${gas:<10} {m.theta:<10.4f} {m.flash_crash_prob:<10.6f} "
              f"{m.phi_m:<8.4f} {m.fundamental_value:<14.4f} {m.speculative_premium:.4f}")
    except ValueError:
        print(f"  ${gas:<10} COLLAPSE")

print()

# Proposition 12(i): P decreases as phi_m falls (liquidity drain = inflation analogue)
print("Liquidity stress (phi_m down -> P down):")
print(f"{'Liquidity %':<14} {'phi_m':<8} {'theta':<10} {'Fund. Value':<14} {'Spec. Premium'}")
print("-" * 65)
for pct in [1.00, 0.80, 0.60, 0.40, 0.20, 0.10, 0.05]:
    depth = total_debt * pct
    try:
        m = calibrate_from_positions(positions, 80, depth, 0.05)
        print(f"  {int(pct*100)}%{'':<11} {m.phi_m:<8.4f} {m.theta:<10.4f} "
              f"{m.fundamental_value:<14.4f} {m.speculative_premium:.4f}")
    except ValueError:
        print(f"  {int(pct*100)}%{'':<11} COLLAPSE")