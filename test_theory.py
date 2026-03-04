import numpy as np
from fetch_aave import generate_aave_positions
from theory import calibrate_from_positions

positions = generate_aave_positions(n=1000)
total_debt = positions['debt_usd'].sum()
stablecoin_depth = total_debt * 0.40
gas_baseline = 80.0

model = calibrate_from_positions(
    positions_df=positions,
    gas_usd=gas_baseline,
    stablecoin_depth_usd=stablecoin_depth,
    daily_volatility=0.05
)

print("=== Pool Statistics ===")
print(f"Total debt in pool:         ${total_debt:,.0f}")
print(f"Liquidation capital (40%):  ${stablecoin_depth:,.0f}")
print(f"Gas cost per liquidation:   ${gas_baseline}")

print("\n=== Model Parameters ===")
print(f"kappa  (normalised gas):    {model.kappa:.8f}")
print(f"phi_m  (liquidity ratio):   {model.phi_m:.4f}")
print(f"Gamma  (price half-width):  {model.Gamma:.4f}")
print(f"phi_m * Gamma / kappa:      {(model.phi_m * model.Gamma / model.kappa):.2f}")

print("\n=== Equilibrium Summary ===")
for k, v in model.summary().items():
    print(f"  {k:<30} {v}")

print("\n=== Conservation Law Check ===")
for k, v in model.conservation_law.items():
    print(f"  {k:<30} {v}")

# Proposition 11: gas stress
print("\n=== Gas Stress Scenarios (Proposition 11: kappa up -> F up) ===")
print(f"{'Gas Cost':<12} {'kappa':<14} {'theta':<10} {'F':<12} {'Status'}")
print("-" * 60)
for gas in [20, 50, 80, 150, 300, 500, 1000, 2000]:
    try:
        m = calibrate_from_positions(positions, gas, stablecoin_depth, 0.05)
        print(f"  ${gas:<10} {m.kappa:<14.8f} {m.theta:<10.4f} "
              f"{m.flash_crash_prob:<12.6f} {m.summary()['market status']}")
    except ValueError:
        print(f"  ${gas:<10} {'---':<14} {'---':<10} {'COLLAPSE':<12}")

# Proposition 11: liquidity stress (phi_m down -> F up)
print("\n=== Liquidity Stress Scenarios (Proposition 11: phi_m down -> F up) ===")
print(f"{'Liquidity %':<14} {'phi_m':<10} {'theta':<10} {'F':<12} {'Status'}")
print("-" * 60)
for pct in [0.80, 0.60, 0.40, 0.20, 0.10, 0.05, 0.02]:
    depth = total_debt * pct
    try:
        m = calibrate_from_positions(positions, gas_baseline, depth, 0.05)
        print(f"  {int(pct*100)}%{'':<11} {m.phi_m:<10.4f} {m.theta:<10.4f} "
              f"{m.flash_crash_prob:<12.6f} {m.summary()['market status']}")
    except ValueError:
        print(f"  {int(pct*100)}%{'':<11} {'---':<10} {'---':<10} {'COLLAPSE':<12}")