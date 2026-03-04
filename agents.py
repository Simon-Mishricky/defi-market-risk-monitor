class BorrowerAgent:
    """
    Represents a single borrower position in a DeFi lending protocol.
    
    Parameters
    ----------
    agent_id         : unique identifier
    collateral_usd   : value of posted collateral in USD
    debt_usd         : outstanding debt in USD
    liq_threshold    : health factor threshold below which liquidation triggers (Aave default 0.825)
    liq_bonus        : bonus paid to liquidator as % of seized collateral (Aave default 5%)
    """
    
    def __init__(self, agent_id, collateral_usd, debt_usd, 
                 liq_threshold=0.825, liq_bonus=0.05):
        self.id = agent_id
        self.collateral = collateral_usd
        self.debt = debt_usd
        self.liq_threshold = liq_threshold
        self.liq_bonus = liq_bonus
        self.liquidated = False

    @property
    def health_factor(self):
        """HF = (collateral * liquidation_threshold) / debt"""
        if self.debt == 0:
            return float('inf')
        return (self.collateral * self.liq_threshold) / self.debt

    def is_liquidatable(self):
        return self.health_factor < 1.0 and not self.liquidated

    def apply_price_shock(self, price_ratio):
        """
        Adjust collateral value after a price move.
        price_ratio = new_price / old_price
        e.g. a 20% drop -> price_ratio = 0.80
        """
        self.collateral *= price_ratio

    def __repr__(self):
        status = "LIQUIDATED" if self.liquidated else f"HF={self.health_factor:.3f}"
        return f"Agent({self.id} | collateral=${self.collateral:,.0f} | debt=${self.debt:,.0f} | {status})"