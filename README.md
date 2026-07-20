# UKB IRA Playbook v2.17 Dashboard

Visual dashboard that runs every rule in the playbook automatically.

## Setup (one time)

1. Create a **private** repository on GitHub (private keeps your data secure)
2. Upload these files to the repository
3. Go to Settings → Pages → Source: **GitHub Actions**
4. Go to Settings → Actions → General → Workflow permissions: **Read and write**

## Weekly Usage (30 seconds)

1. Download your Fidelity CSV: Accounts → Portfolio → Download
2. Rename it `portfolio.csv`
3. Drag it into the GitHub repository (or `git push`)
4. Dashboard regenerates automatically in ~60 seconds
5. View at: `https://[your-username].github.io/[repo-name]/`

## What It Shows

| Panel | Rules |
|---|---|
| KPI Strip | Account value, drawdown, VIX, SKEW, SPAXX |
| Action Alerts | Rule 14, Section 19 clock, Rule 20, VIX triggers |
| Section 24 Heat Monitor | VIX gauge, SKEW gauge, HY spreads, drawdown |
| Section 19 Clocks | Progress bar + days remaining per investigation |
| SNDK Gaps | Which conviction names need more capital |
| RSI Bot Positions | Entry/stop/target for open tactical positions |
| Full Position Table | Rule 3 score, Rule 29 tier, Rule 4 status, SNDK per position |

## Manual Local Run

```bash
pip install -r requirements.txt
python dashboard.py portfolio.csv
# Opens index.html in current directory
```

## Updating Knowledge Base

Edit `dashboard.py` — the top section contains:
- `RULE3_SCORES`: update when re-scoring a position
- `SECTION19_OPEN`: add/remove active Section 19 investigations
- `THREE_PILLARS`: update monthly Three Pillars scores
- `RSI_BOT_POSITIONS`: update when bot positions open/close
- `PEAK`: update after a new all-time high
