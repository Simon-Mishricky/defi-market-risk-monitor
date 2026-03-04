from agents import BorrowerAgent

# Create a single test agent
agent = BorrowerAgent(
    agent_id=0,
    collateral_usd=10000,
    debt_usd=5000
)

print("--- Before price shock ---")
print(agent)
print(f"Liquidatable: {agent.is_liquidatable()}")

# Apply a 30% price drop to collateral
agent.apply_price_shock(0.70)

print("\n--- After 30% price drop ---")
print(agent)
print(f"Liquidatable: {agent.is_liquidatable()}")

# Apply another 20% drop
agent.apply_price_shock(0.80)

print("\n--- After another 20% drop ---")
print(agent)
print(f"Liquidatable: {agent.is_liquidatable()}")