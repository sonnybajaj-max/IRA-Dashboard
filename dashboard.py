import streamlit as st
import pandas as pd
import numpy as np

# Set Streamlit Page Config
st.set_page_config(
    page_title="UKB IRA - Playbook v2.18 Executive Dashboard",
    layout="wide",
    initial_sidebar_state="expanded"
)

# -----------------------------------------------------------------------------
# CONSTANTS & V2.18 PLAYBOOK CONFIGURATION
# -----------------------------------------------------------------------------
PEAK_PORTFOLIO_VAL = 1433927.00
BASELINE_AUG_2026 = 1393234.00

TIER_CONFIG = {
    "T1 Compound Engines": {
        "target": 0.40,
        "band": (0.35, 0.45),
        "members": ["NVDA", "AVGO", "GOOG", "MSFT", "CRWD", "AMZN"]
    },
    "T2 ETF Sleeve": {
        "target": 0.28,
        "band": (0.25, 0.35),
        "members": ["VGT", "QQQM", "SPY", "SOXX"]
    },
    "T3 Semi Thesis": {
        "target": 0.08,
        "band": (0.06, 0.10),
        "members": ["TER", "MU", "COHR", "TSM"]
    },
    "T4 Active Review": {
        "target": 0.02, # Five-year goal <5%
        "band": (0.00, 0.08),
        "members": ["META", "CRM", "PLTR", "AAPL", "ARM", "QCOM", "MP"]
    },
    "T5 Diversifiers": {
        "target": 0.12,
        "band": (0.08, 0.15),
        "members": ["LLY", "GEV", "JPM", "UNH", "JEPQ", "ENB", "GLD", "VRT", "RTX", "O", "NOW", "PANW", "AMD", "ORCL"]
    },
    "T6 Cash": {
        "target": 0.02,
        "band": (0.01, 0.03),
        "members": ["SPAXX"]
    }
}

RULE_20_THRESHOLDS = {
    "-8% (Quartile Review)": PEAK_PORTFOLIO_VAL * 0.92,   # $1,319,213
    "-12% (15% Cash / Pause Buys)": PEAK_PORTFOLIO_VAL * 0.88, # $1,261,856
    "-15% (Cut Thematics / 45% Growth)": PEAK_PORTFOLIO_VAL * 0.85, # $1,218,838
    "-20% (Risk-Off Major Review)": PEAK_PORTFOLIO_VAL * 0.80  # $1,147,142
}

# -----------------------------------------------------------------------------
# HELPER FUNCTIONS
# -----------------------------------------------------------------------------
def classify_tier(ticker):
    """Maps a ticker to its Rule 32 Tier."""
    ticker_clean = ticker.strip().upper()
    for tier_name, config in TIER_CONFIG.items():
        if ticker_clean in config["members"]:
            return tier_name
    return "T5 Diversifiers" # Default fallback for unlisted positions

def calculate_tier_drift(df_portfolio, total_value):
    """Calculates allocation metrics and drift status for each tier."""
    tier_summary = []
    
    df_portfolio["Tier"] = df_portfolio["Ticker"].apply(classify_tier)
    grouped = df_portfolio.groupby("Tier")["Value"].sum()
    
    for tier_name, config in TIER_CONFIG.items():
        val = grouped.get(tier_name, 0.0)
        pct = val / total_value if total_value > 0 else 0.0
        min_b, max_b = config["band"]
        
        if pct < min_b:
            status = "BELOW BAND"
        elif pct > max_b:
            status = "ABOVE BAND"
        else:
            status = "IN BAND"
            
        tier_summary.append({
            "Tier": tier_name,
            "Current Value": val,
            "Current %": pct,
            "Target %": config["target"],
            "Min Band %": min_b,
            "Max Band %": max_b,
            "Status": status
        })
        
    return pd.DataFrame(tier_summary)

def evaluate_capital_routing(tier_df):
    """Executes the Rule 32 Capital Routing Decision Tree for Active Review exits."""
    tier_map = tier_df.set_index("Tier")["Current %"].to_dict()
    
    t1_pct = tier_map.get("T1 Compound Engines", 0.0)
    t2_pct = tier_map.get("T2 ETF Sleeve", 0.0)
    t4_pct = tier_map.get("T4 Active Review", 0.0)
    t5_pct = tier_map.get("T5 Diversifiers", 0.0)
    
    # Capital Routing Decision Tree (Evaluated in sequential order)
    if t4_pct > 0.10:
        return "Step 1: T4 Active Review > 10%", "100% SPAXX (Hold proceeds until T4 < 8%)"
    elif t1_pct < 0.35:
        return "Step 2: T1 Compound Engines < 35%", "60% VGT / 40% Weakest CE Add (CRWD)"
    elif t2_pct < 0.25:
        return "Step 3: T2 ETF Sleeve < 25%", "100% VGT (Accelerate VGT build)"
    elif t5_pct > 0.15:
        return "Step 4: T5 Diversifiers > 15%", "100% VGT (Do not add to Diversifiers)"
    else:
        return "Step 5: All Tiers In Band", "70% VGT / 30% CE Split"

# -----------------------------------------------------------------------------
# MAIN APP DASHBOARD
# -----------------------------------------------------------------------------
st.title(" UKB IRA - Playbook v2.18 Executive Dashboard")
st.caption("Effective: August 2026 | Peak: $1,433,927 | Account: 250718173")

# Sidebar - Sample Portfolio Data Input / Upload
st.sidebar.header("Portfolio Inputs")
uploaded_file = st.sidebar.file_uploader("Upload Portfolio CSV", type=["csv"])

if uploaded_file:
    df = pd.read_csv(uploaded_file)
else:
    # Default sample data matching v2.18 August 2026 current state
    sample_data = {
        "Ticker": ["NVDA", "AVGO", "GOOG", "MSFT", "CRWD", "AMZN", "VGT", "QQQM", "SPY", "SOXX",
                   "TER", "MU", "COHR", "TSM", "META", "CRM", "PLTR", "AAPL", "MP", "GLD", "ENB", "SPAXX"],
        "Value": [120000, 110000, 80000, 60000, 47650, 38000, 250000, 50000, 35000, 27000,
                  30000, 32000, 20000, 20000, 40000, 45000, 35000, 20000, 20200, 142000, 149000, 22384]
    }
    df = pd.DataFrame(sample_data)

total_portfolio_val = df["Value"].sum()

# Top Key Performance Indicators
col1, col2, col3, col4 = st.columns(4)
col1.metric("Current Portfolio Value", f"${total_portfolio_val:,.2f}")
col2.metric("Peak Benchmark Value", f"${PEAK_PORTFOLIO_VAL:,.2f}")
drawdown_from_peak = ((total_portfolio_val - PEAK_PORTFOLIO_VAL) / PEAK_PORTFOLIO_VAL) * 100
col3.metric("Peak Drawdown", f"{drawdown_from_peak:.2f}%")
col4.metric("Rule 13 Min CAGR Target", "11.18%")

st.markdown("---")

# Section 1: Rule 32 Tier Drift Analysis
st.subheader("§17 Rule 32 - Institutional Tier Drift Monitor")

tier_df = calculate_tier_drift(df, total_portfolio_val)

# Capital Routing Recommendation Banner
step_name, routing_action = evaluate_capital_routing(tier_df)
st.info(f"**Active Review Exit Capital Routing Directive ({step_name}):**\n\n➡ **{routing_action}**")

# Display Tier Metrics
formatted_tier_df = tier_df.copy()
formatted_tier_df["Current Value"] = formatted_tier_df["Current Value"].map("${:,.2f}".format)
formatted_tier_df["Current %"] = (formatted_tier_df["Current %"] * 100).map("{:.2f}%".format)
formatted_tier_df["Target %"] = (formatted_tier_df["Target %"] * 100).map("{:.1f}%".format)
formatted_tier_df["Min Band %"] = (formatted_tier_df["Min Band %"] * 100).map("{:.1f}%".format)
formatted_tier_df["Max Band %"] = (formatted_tier_df["Max Band %"] * 100).map("{:.1f}%".format)

st.dataframe(formatted_tier_df, use_container_width=True)

st.markdown("---")

# Section 2: Rule 20 Portfolio Heat & Drawdown Triggers
st.subheader("§7 Rule 20 - Portfolio Heat Thresholds")

heat_summary = []
for level, trigger_val in RULE_20_THRESHOLDS.items():
    is_triggered = total_portfolio_val <= trigger_val
    heat_summary.append({
        "Drawdown Level": level,
        "Trigger Portfolio Value": f"${trigger_val:,.2f}",
        "Current Delta": f"${total_portfolio_val - trigger_val:,.2f}",
        "Status": "🚨 TRIGGERED" if is_triggered else "🟢 SAFE"
    })

st.table(pd.DataFrame(heat_summary))

st.markdown("---")

# Section 3: Priority Hierarchy & Rule 22 Logging Template
col_left, col_right = st.columns(2)

with col_left:
    st.subheader("§1 Rule Priority Hierarchy (v2.18)")
    hierarchy_data = [
        ("1 - Highest", "Rule 20: Portfolio Heat & Stress Test"),
        ("2", "Rule 4: Revenue Inflection Protection"),
        ("3", "Rule 18/18B: Macro Regime & Transition"),
        ("4", "Rule 19: Valuation/Liquidity Override"),
        ("5", "Rule 1: Position Caps"),
        ("8", "Rule 8c: 200DMA Confirmation"),
        ("8.5 (NEW)", "Rule 32: Tier Drift Protocol"),
        ("9", "Rule 14: Gain Ladder / Rule 25 Opportunity Cost"),
        ("10 - Lowest", "Rule 17: Quarterly Rebalancing")
    ]
    st.table(pd.DataFrame(hierarchy_data, columns=["Priority", "Rule Focus"]))

with col_right:
    st.subheader("§18 Rule 22 Journal Generator")
    with st.form("rule_22_form"):
        ticker = st.text_input("Ticker Symbol", "CRM")
        trigger = st.text_input("Trigger Rule", "Section 19 Step 3 Clock Expiry")
        decision = st.text_input("Decision Executed", "Trim position by 30%")
        r32_route = st.text_input("Rule 32 Capital Route", "60% VGT / 40% CRWD")
        review_date = st.date_input("90-Day Review Date")
        
        submitted = st.form_submit_button("Generate Rule 22 Journal Entry")
        if submitted:
            st.code(f"""
=== RULE 22 JOURNAL ENTRY ===
Date: {pd.Timestamp.now().strftime('%Y-%m-%d')}
Ticker: {ticker.upper()}
Trigger: {trigger}
Decision: {decision}
Rule 32 Routing: {r32_route}
90-Day Review Date: {review_date}
Status: RECORDED
            """, language="yaml")
