import matplotlib.pyplot as plt
from fetch_aave import generate_aave_positions
from theory import calibrate_from_positions

positions = generate_aave_positions(n=1000)
total_debt = positions['debt_usd'].sum()

# --- Plot 1: baseline ---
m1 = calibrate_from_positions(positions, 80, total_debt * 0.40, 0.05)

# --- Plot 2: high gas (kappa stress) ---
m2 = calibrate_from_positions(positions, 2000, total_debt * 0.40, 0.05)

# --- Plot 3: low liquidity (phi_m stress) ---
m3 = calibrate_from_positions(positions, 80, total_debt * 0.05, 0.05)

fig1 = m1.plot_distributions(title=f"Baseline | theta={m1.theta:.2f} | F={m1.flash_crash_prob:.4f}")
fig2 = m2.plot_distributions(title=f"Gas Stress ($2000) | theta={m2.theta:.2f} | F={m2.flash_crash_prob:.4f}")
fig3 = m3.plot_distributions(title=f"Liquidity Stress (5%) | theta={m3.theta:.2f} | F={m3.flash_crash_prob:.4f}")

fig1.savefig("dist_baseline.png", dpi=150)
fig2.savefig("dist_gas_stress.png", dpi=150)
fig3.savefig("dist_liquidity_stress.png", dpi=150)

print("Saved 3 distribution plots.")
print(f"\nBaseline:         theta={m1.theta:.4f}  F={m1.flash_crash_prob:.6f}  CV={m1.cv_bid:.6f}")
print(f"Gas stress:       theta={m2.theta:.4f}  F={m2.flash_crash_prob:.6f}  CV={m2.cv_bid:.6f}")
print(f"Liquidity stress: theta={m3.theta:.4f}  F={m3.flash_crash_prob:.6f}  CV={m3.cv_bid:.6f}")