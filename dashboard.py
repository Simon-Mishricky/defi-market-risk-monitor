import dash
from dash import dcc, html, Input, Output, ctx
import plotly.graph_objects as go
import pandas as pd
import numpy as np
from simulate import run_cascade
from theory import calibrate_from_positions
from fetch_aave import generate_aave_positions
try:
    from fetch_live import fetch_live_positions, check_connection
    LIVE_AVAILABLE = True
except (ImportError, Exception):
    LIVE_AVAILABLE = False

app = dash.Dash(__name__)

app.layout = html.Div([

    html.H1("DeFi Liquidation Risk Simulator",
            style={"textAlign": "center", "fontFamily": "Arial", "marginBottom": "10px"}),

    html.P("Mishricky (2025) — Asset Price Dispersion, Monetary Policy and Macroprudential Regulation",
           style={"textAlign": "center", "fontFamily": "Arial", "color": "grey", "marginBottom": "10px"}),

    html.Div([
        html.Label("Data Source: ", style={"fontFamily": "Arial", "fontSize": "14px", "marginRight": "10px"}),
        dcc.RadioItems(
            id="data-source",
            options=[
                {"label": "  Synthetic (offline)", "value": "synthetic"},
                {"label": "  Live Aave V3", "value": "live"},
            ],
            value="synthetic",
            inline=True,
            style={"fontFamily": "Arial", "fontSize": "14px", "display": "inline-block"}
        ),
        html.Span(id="data-source-status",
                  style={"fontFamily": "Arial", "fontSize": "13px",
                         "color": "#555", "marginLeft": "20px", "fontStyle": "italic"}),
    ], style={"textAlign": "center", "marginBottom": "20px"}),

    html.Div([
        html.Div([
            html.Label("Crisis Scenario Preset"),
            dcc.RadioItems(
                id="scenario-preset",
                options=[
                    {"label": "  Normal market", "value": "normal"},
                    {"label": "  Liquidity crisis", "value": "liquidity"},
                    {"label": "  Gas spike", "value": "gas"},
                    {"label": "  Combined shock (2022-style)", "value": "combined"},
                ],
                value="normal",
                inline=True,
                style={"fontFamily": "Arial", "fontSize": "14px"}
            ),
        ], style={"marginBottom": "10px"}),

        html.P(id="preset-description",
               style={"fontFamily": "Arial", "fontSize": "13px",
                      "color": "#555", "fontStyle": "italic", "marginBottom": "20px"}),

        html.Div([
            html.Label("Price Drop (%)"),
            dcc.Slider(id="price-drop", min=5, max=60, step=5, value=30,
                       marks={i: f"{i}%" for i in range(5, 65, 5)}),
        ], style={"marginBottom": "30px"}),

        html.Div([
            html.Label("Initial Liquidity (% of total debt)"),
            dcc.Slider(id="liquidity-pct", min=1, max=80, step=1, value=40,
                       marks={i: f"{i}%" for i in [1, 5, 10, 20, 40, 60, 80]}),
        ], style={"marginBottom": "30px"}),

        html.Div([
            html.Label("Gas Cost per Liquidation (USD)"),
            dcc.Slider(id="gas-cost", min=20, max=500, step=20, value=80,
                       marks={i: f"${i}" for i in range(20, 520, 80)}),
        ], style={"marginBottom": "30px"}),

    ], style={"padding": "20px", "backgroundColor": "#f9f9f9",
              "borderRadius": "8px", "marginBottom": "30px"}),

    html.Div(id="summary-stats",
             style={"display": "flex", "justifyContent": "space-around",
                    "flexWrap": "wrap", "gap": "10px",
                    "marginBottom": "30px", "fontFamily": "Arial"}),

    html.Div([
        dcc.Graph(id="cascade-chart"),
        dcc.Graph(id="theory-chart"),
    ], style={"display": "grid", "gridTemplateColumns": "1fr 1fr", "gap": "20px"}),

    html.Div([
        dcc.Graph(id="distributions-chart"),
        dcc.Graph(id="stress-test-chart"),
    ], style={"display": "grid", "gridTemplateColumns": "1fr 1fr",
              "gap": "20px", "marginTop": "20px"}),

], style={"maxWidth": "1400px", "margin": "auto", "padding": "20px"})


@app.callback(
    Output("price-drop", "value"),
    Output("liquidity-pct", "value"),
    Output("gas-cost", "value"),
    Output("preset-description", "children"),
    Output("summary-stats", "children"),
    Output("cascade-chart", "figure"),
    Output("theory-chart", "figure"),
    Output("distributions-chart", "figure"),
    Output("stress-test-chart", "figure"),
    Output("data-source-status", "children"),
    Input("scenario-preset", "value"),
    Input("price-drop", "value"),
    Input("liquidity-pct", "value"),
    Input("gas-cost", "value"),
    Input("data-source", "value"),
)
def update_dashboard(scenario_preset, price_drop, liquidity_pct, gas_cost, data_source):

    preset_map = {
        "normal":    (30, 40, 80),
        "liquidity": (30, 3, 80),
        "gas":       (30, 40, 450),
        "combined":  (45, 5, 400),
    }

    preset_descriptions = {
        "normal":    "Baseline conditions. 30% price drop, 40% liquidity depth, $80 gas. Moderate φᵐ and low κ.",
        "liquidity": "φᵐ shock. Liquidity depth reduced to 3% of total debt, simulating capital flight before the crash.",
        "gas":       "κ shock. Gas cost raised to $450, raising flash crash risk as posting becomes more costly. Large positions remain profitable to liquidate — the scenario demonstrates how κ elevates F even without generating bad debt.",
        "combined":  "Simultaneous φᵐ collapse and κ shock with a 45% price drop. Analogue of March 2020 or November 2022.",
    }

    if ctx.triggered_id == "scenario-preset":
        price_drop, liquidity_pct, gas_cost = preset_map[scenario_preset]

    description = preset_descriptions.get(scenario_preset, "")

    print(f"Running: preset={scenario_preset} drop={price_drop}% liquidity={liquidity_pct}% gas=${gas_cost}")

    # --- Generate pool (shared across pre-cascade calibration and chart 3) ---
    data_status = ""
    if data_source == "live" and LIVE_AVAILABLE:
        try:
            positions = fetch_live_positions(n_sample=1000)
            data_status = f"Live Aave V3 — {len(positions)} positions fetched"
        except Exception as e:
            positions = generate_aave_positions(n=1000)
            data_status = f"Live fetch failed ({e}) — using synthetic data"
    else:
        positions = generate_aave_positions(n=1000)
        data_status = "Synthetic data (Aave V3 calibrated)" if data_source == "synthetic" else "Live data unavailable — using synthetic"
    total_debt = positions['debt_usd'].sum()
    stablecoin_depth = total_debt * (liquidity_pct / 100)

    # --- Pre-cascade initial F (before any liquidations occur) ---
    try:
        initial_model = calibrate_from_positions(positions, float(gas_cost), stablecoin_depth, 0.05)
        initial_F = initial_model.flash_crash_prob
        initial_theta = initial_model.theta
        initial_status = initial_model.summary()["market status"]
    except ValueError:
        initial_F = 1.0
        initial_theta = 0.0
        initial_status = "COLLAPSE"

    # --- Run simulation ---
    results, agents = run_cascade(
        price_drop_pct=price_drop / 100,
        gas_usd=float(gas_cost),
        initial_liquidity_pct=liquidity_pct / 100
    )

    total_liquidated = sum(1 for a in agents if a.liquidated)
    total_bad_debt = results['bad_debt_usd'].sum()
    final_F = results['F (crash prob)'].iloc[-1]
    final_status = results['market_status'].iloc[-1]

    def status_color(s):
        return {"STABLE": "green", "ELEVATED RISK": "orange",
                "CRITICAL": "red"}.get(s, "grey")

    def stat_box(label, value, color="black"):
        return html.Div([
            html.H3(value, style={"color": color, "margin": "0", "fontSize": "24px"}),
            html.P(label, style={"margin": "0", "color": "grey", "fontSize": "12px"})
        ], style={"textAlign": "center", "padding": "15px",
                  "backgroundColor": "white", "borderRadius": "8px",
                  "boxShadow": "0 2px 4px rgba(0,0,0,0.1)", "minWidth": "150px"})

    summary = [
        stat_box("Positions Liquidated", f"{total_liquidated} / 1000"),
        stat_box("Bad Debt", f"${total_bad_debt/1e6:.1f}M",
                 color="red" if total_bad_debt > 0 else "green"),
        stat_box("Cascade Rounds", str(len(results))),
        stat_box("Initial F (pre-cascade)", f"{initial_F:.7f}"),
        stat_box("Final F (post-cascade)", f"{final_F:.7f}"),
        stat_box("Initial Status", initial_status, color=status_color(initial_status)),
        stat_box("Final Status", final_status, color=status_color(final_status)),
    ]

    # --- Chart 1: Cascade ---
    fig1 = go.Figure()
    fig1.add_trace(go.Bar(
        x=results['round'], y=results['liquidations'],
        name='Liquidations', marker_color='crimson', yaxis='y'
    ))
    fig1.add_trace(go.Scatter(
        x=results['round'], y=results['price'],
        name='Price', line=dict(color='steelblue', width=2), yaxis='y2'
    ))
    fig1.update_layout(
        title="Liquidation Cascade by Round", xaxis_title="Round",
        yaxis=dict(title="Liquidations", side="left"),
        yaxis2=dict(title="Price (relative)", side="right", overlaying="y"),
        legend=dict(x=0.7, y=0.99), template="plotly_white"
    )

    # --- Chart 2: Theory ---
    # Prepend round 0 (pre-cascade) so the chart shows the full trajectory
    rounds = [0] + list(results['round'])
    thetas = [initial_theta] + list(results['theta'])
    fs     = [initial_F]     + list(results['F (crash prob)'])

    fig2 = go.Figure()
    fig2.add_trace(go.Scatter(
        x=rounds, y=thetas,
        name='θ (quote intensity)', line=dict(color='green', width=2), yaxis='y'
    ))
    fig2.add_trace(go.Scatter(
        x=rounds, y=fs,
        name='F (flash crash prob)',
        line=dict(color='red', width=2, dash='dash'), yaxis='y2'
    ))
    fig2.update_layout(
        title="Mishricky (2025): θ and F During Cascade", xaxis_title="Round",
        xaxis=dict(tickvals=rounds, ticktext=["Pre"] + [str(r) for r in results['round']]),
        yaxis=dict(title="θ (quote intensity)", side="left"),
        yaxis2=dict(title="F (flash crash probability)", side="right", overlaying="y"),
        legend=dict(x=0.5, y=0.99), template="plotly_white"
    )

    # --- Chart 3: Distributions (calibrated to pre-cascade initial conditions) ---
    try:
        model = initial_model

        p_hat = 1.0
        ask_lower = p_hat + model.kappa / model.phi_m
        ask_upper = p_hat + model.Gamma
        bid_lower = p_hat - model.Gamma
        bid_upper = p_hat - model.kappa / model.phi_m

        prices_ask = np.linspace(ask_lower, ask_upper, 300)
        prices_bid = np.linspace(bid_lower, bid_upper, 300)

        ask_cdf = [model.ask_distribution(p) for p in prices_ask]
        bid_cdf = [model.bid_distribution(p) for p in prices_bid]
        ask_pdf = np.gradient(ask_cdf, prices_ask)
        bid_pdf = np.gradient(bid_cdf, prices_bid)

        fig3 = go.Figure()
        fig3.add_trace(go.Scatter(
            x=prices_ask, y=ask_pdf, fill='tozeroy', name='Ask density',
            line=dict(color='red'), fillcolor='rgba(255,0,0,0.2)'
        ))
        fig3.add_trace(go.Scatter(
            x=prices_bid, y=bid_pdf, fill='tozeroy', name='Bid density',
            line=dict(color='blue'), fillcolor='rgba(0,0,255,0.2)'
        ))
        fig3.add_vline(
            x=ask_lower, line_dash="dash", line_color="darkred")
        
        fig3.add_vline(
            x=bid_upper, line_dash="dash", line_color="darkblue")
        
        fig3.update_layout(
            title=f"Proposition 1: Bid & Ask Distributions  |  θ={model.theta:.2f}  |  F={model.flash_crash_prob:.7f}  |  {model.summary()['market status']}",
            xaxis_title="Price", yaxis_title="Density",
            xaxis=dict(range=[bid_lower - 0.001, ask_upper + 0.001]),
            template="plotly_white"
        )
        fig3.update_yaxes(range=[0, min(max(ask_pdf), max(bid_pdf)) * 0.05])

    except (ValueError, AttributeError):
        fig3 = go.Figure()
        fig3.add_annotation(
            text="Market collapse — no quoting activity",
            xref="paper", yref="paper", x=0.5, y=0.5,
            showarrow=False, font=dict(size=16, color="red")
        )
        fig3.update_layout(
            title="Proposition 1: Bid & Ask Price Distributions",
            template="plotly_white"
        )

    # --- Chart 4: Stress test ---
    drops = [0.05, 0.10, 0.15, 0.20, 0.25, 0.30, 0.35, 0.40, 0.45, 0.50]
    scenario_results = []
    for d in drops:
        try:
            r, a = run_cascade(
                price_drop_pct=d,
                gas_usd=float(gas_cost),
                initial_liquidity_pct=liquidity_pct / 100
            )
            scenario_results.append({
                "drop": f"{int(d*100)}%",
                "liquidated": sum(1 for x in a if x.liquidated),
                "bad_debt": r['bad_debt_usd'].sum() / 1e6,
            })
        except Exception:
            scenario_results.append({
                "drop": f"{int(d*100)}%",
                "liquidated": 1000,
                "bad_debt": 0,
            })

    scenario_df = pd.DataFrame(scenario_results)

    fig4 = go.Figure()
    fig4.add_trace(go.Bar(
        x=scenario_df['drop'], y=scenario_df['bad_debt'],
        name='Bad Debt ($M)', marker_color='crimson', yaxis='y'
    ))
    fig4.add_trace(go.Scatter(
        x=scenario_df['drop'], y=scenario_df['liquidated'],
        name='Positions Liquidated',
        line=dict(color='steelblue', width=2), yaxis='y2'
    ))
    fig4.update_layout(
        title="Stress Test: All Scenarios", xaxis_title="Price Drop",
        yaxis=dict(title="Bad Debt ($M)", side="left"),
        yaxis2=dict(title="Positions Liquidated", side="right", overlaying="y"),
        legend=dict(x=0.01, y=0.99), template="plotly_white"
    )

    return price_drop, liquidity_pct, gas_cost, description, summary, fig1, fig2, fig3, fig4, data_status


if __name__ == "__main__":
    app.run(debug=True)
