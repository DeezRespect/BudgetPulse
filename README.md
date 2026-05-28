# BudgetPulse — Personal Finance Analyzer

A lightweight personal finance analyzer built in Python + vanilla JS.
No external dependencies for the dashboard — just open `index.html` in a browser.

## Features

- **Monthly summary** — income, expenses, savings, savings rate
- **Category breakdown** — where your money actually goes
- **Anomaly detection** — flags expense spikes vs. rolling average
- **Stop-loss alerts** — categories exceeding budget thresholds
- **Savings goal tracker** — ETA to your target based on recent average
- **CSV import** — works with any transaction export

## Python Script

```bash
# Basic usage
python analyze.py --file transactions.csv --goal 6000

# With category filter and JSON export
python analyze.py --file transactions.csv --goal 6000 --months 3 --export report.json
```

### CSV Format

```
date,description,amount,category,type
2026-01-15,Salary,150000,Income,income
2026-01-20,Rent,-45000,Housing,expense
```

- `date` — YYYY-MM-DD
- `amount` — negative for expenses, positive for income
- `type` — `income` or `expense`

## Dashboard

Open `index.html` in any browser. Click **Load Demo** to see sample data,
or **Import CSV** to load your own transactions.

## Project Structure

```
budgetpulse/
├── analyze.py        # Python CLI analyzer
├── transactions.csv  # Sample data
├── index.html        # Interactive dashboard
└── README.md
```

## Stack

- Python 3.11+ (stdlib only — csv, json, statistics, argparse)
- Vanilla JS + HTML/CSS (zero dependencies)
