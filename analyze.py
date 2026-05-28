"""
BudgetPulse — Personal Finance Analyzer
----------------------------------------
Reads a CSV of transactions and generates a full financial report:
  - Monthly summary (income, expenses, savings rate)
  - Spending breakdown by category
  - Anomaly detection (unusual spikes vs. rolling average)
  - Savings goal tracker
  - Stop-loss alerts (categories bleeding budget)

Usage:
    python analyze.py --file transactions.csv --goal 6000 --months 3
    python analyze.py --file transactions.csv --goal 6000 --export report.json

CSV format (headers required):
    date,description,amount,category,type
    2026-01-15,Gym membership,-4500,Health,expense
    2026-01-20,Salary,150000,Income,income

Amounts in your local currency. Negative = expense, positive = income.
"""

import argparse
import csv
import json
import os
import sys
from collections import defaultdict
from datetime import datetime
from statistics import mean, stdev


# ─── CONFIG ───────────────────────────────────────────────────────────────────

STOP_LOSS_THRESHOLD = 0.30   # Alert if category > 30% of total expenses
SPIKE_MULTIPLIER    = 1.8    # Alert if month > 1.8x rolling average
SAVINGS_WARN_RATE   = 0.10   # Warn if savings rate drops below 10%


# ─── LOAD & PARSE ─────────────────────────────────────────────────────────────

def load_csv(filepath: str) -> list[dict]:
    if not os.path.exists(filepath):
        print(f"[ERROR] File not found: {filepath}")
        sys.exit(1)

    transactions = []
    with open(filepath, newline='', encoding='utf-8') as f:
        reader = csv.DictReader(f)
        required = {'date', 'description', 'amount', 'category', 'type'}
        if not required.issubset(set(reader.fieldnames or [])):
            print(f"[ERROR] CSV must have columns: {required}")
            sys.exit(1)

        for i, row in enumerate(reader, 2):
            try:
                transactions.append({
                    'date':        datetime.strptime(row['date'].strip(), '%Y-%m-%d'),
                    'description': row['description'].strip(),
                    'amount':      float(row['amount'].strip()),
                    'category':    row['category'].strip(),
                    'type':        row['type'].strip().lower(),
                })
            except (ValueError, KeyError) as e:
                print(f"[WARN] Skipping row {i}: {e}")

    print(f"[OK] Loaded {len(transactions)} transactions from {filepath}")
    return transactions


# ─── METRICS ──────────────────────────────────────────────────────────────────

def monthly_summary(transactions: list[dict]) -> dict:
    """Group transactions by month and calculate income, expenses, savings."""
    months = defaultdict(lambda: {'income': 0.0, 'expenses': 0.0, 'transactions': []})

    for t in transactions:
        key = t['date'].strftime('%Y-%m')
        months[key]['transactions'].append(t)
        if t['type'] == 'income':
            months[key]['income'] += t['amount']
        else:
            months[key]['expenses'] += abs(t['amount'])

    result = {}
    for month, data in sorted(months.items()):
        income   = data['income']
        expenses = data['expenses']
        savings  = income - expenses
        rate     = (savings / income * 100) if income > 0 else 0
        result[month] = {
            'income':        round(income, 2),
            'expenses':      round(expenses, 2),
            'savings':       round(savings, 2),
            'savings_rate':  round(rate, 1),
            'transactions':  len(data['transactions']),
        }

    return result


def category_breakdown(transactions: list[dict], months_back: int = None) -> dict:
    """Total spending per category, optionally filtered to last N months."""
    if months_back:
        cutoff = sorted(set(t['date'].strftime('%Y-%m') for t in transactions))
        cutoff = cutoff[-months_back] if len(cutoff) >= months_back else cutoff[0]
        transactions = [t for t in transactions if t['date'].strftime('%Y-%m') >= cutoff]

    categories = defaultdict(float)
    for t in transactions:
        if t['type'] == 'expense':
            categories[t['category']] += abs(t['amount'])

    total = sum(categories.values())
    result = {}
    for cat, amount in sorted(categories.items(), key=lambda x: -x[1]):
        result[cat] = {
            'total':   round(amount, 2),
            'percent': round(amount / total * 100, 1) if total > 0 else 0,
        }
    return result


def detect_anomalies(monthly: dict) -> list[dict]:
    """Flag months where expenses spike above the rolling average."""
    months   = list(monthly.keys())
    expenses = [monthly[m]['expenses'] for m in months]
    alerts   = []

    if len(expenses) < 3:
        return alerts  # Not enough data for meaningful comparison

    for i in range(2, len(months)):
        rolling_avg = mean(expenses[:i])
        current     = expenses[i]
        if current > rolling_avg * SPIKE_MULTIPLIER:
            pct = round((current / rolling_avg - 1) * 100, 1)
            alerts.append({
                'month':       months[i],
                'type':        'expense_spike',
                'value':       current,
                'average':     round(rolling_avg, 2),
                'delta_pct':   pct,
                'message':     f"{months[i]}: expenses ${current:,.0f} — {pct}% above rolling avg (${rolling_avg:,.0f})",
            })

        if monthly[months[i]]['savings_rate'] < SAVINGS_WARN_RATE * 100:
            rate = monthly[months[i]]['savings_rate']
            alerts.append({
                'month':   months[i],
                'type':    'low_savings',
                'value':   rate,
                'message': f"{months[i]}: savings rate only {rate}% — below {SAVINGS_WARN_RATE*100:.0f}% threshold",
            })

    return alerts


def stop_loss_check(breakdown: dict) -> list[dict]:
    """Flag categories consuming disproportionate share of total spending."""
    alerts = []
    total  = sum(v['total'] for v in breakdown.values())

    for cat, data in breakdown.items():
        if data['percent'] / 100 > STOP_LOSS_THRESHOLD:
            alerts.append({
                'category': cat,
                'amount':   data['total'],
                'percent':  data['percent'],
                'message':  f"{cat}: {data['percent']}% of total spend (${data['total']:,.0f}) — exceeds {STOP_LOSS_THRESHOLD*100:.0f}% threshold",
            })

    return alerts


def goal_tracker(monthly: dict, goal: float) -> dict:
    """Project time to reach savings goal based on recent average savings."""
    all_months  = list(monthly.values())
    last_3      = all_months[-3:] if len(all_months) >= 3 else all_months
    avg_savings = mean([m['savings'] for m in last_3])
    total_saved = sum(m['savings'] for m in all_months)
    remaining   = max(goal - total_saved, 0)

    months_needed = (remaining / avg_savings) if avg_savings > 0 else float('inf')

    return {
        'goal':           goal,
        'total_saved':    round(total_saved, 2),
        'remaining':      round(remaining, 2),
        'avg_monthly':    round(avg_savings, 2),
        'months_to_goal': round(months_needed, 1) if months_needed != float('inf') else None,
        'on_track':       avg_savings > 0 and remaining > 0,
    }


# ─── REPORT ───────────────────────────────────────────────────────────────────

def build_report(filepath: str, goal: float, months_back: int) -> dict:
    transactions = load_csv(filepath)

    monthly   = monthly_summary(transactions)
    breakdown = category_breakdown(transactions, months_back)
    anomalies = detect_anomalies(monthly)
    stoploss  = stop_loss_check(breakdown)
    tracker   = goal_tracker(monthly, goal) if goal else None

    return {
        'generated_at':     datetime.now().isoformat(),
        'source_file':      filepath,
        'total_transactions': len(transactions),
        'monthly_summary':  monthly,
        'category_breakdown': breakdown,
        'anomalies':        anomalies,
        'stop_loss_alerts': stoploss,
        'goal_tracker':     tracker,
    }


def print_report(report: dict):
    sep = "─" * 56

    print(f"\n{'BudgetPulse Report':^56}")
    print(f"{'Generated: ' + report['generated_at'][:10]:^56}")
    print(sep)

    # Monthly summary
    print("\n📅  MONTHLY SUMMARY")
    print(f"  {'Month':<10} {'Income':>10} {'Expenses':>10} {'Savings':>10} {'Rate':>6}")
    print(f"  {'─'*10} {'─'*10} {'─'*10} {'─'*10} {'─'*6}")
    for month, data in report['monthly_summary'].items():
        flag = " ⚠" if data['savings_rate'] < 10 else ""
        print(f"  {month:<10} {data['income']:>10,.0f} {data['expenses']:>10,.0f} "
              f"{data['savings']:>10,.0f} {data['savings_rate']:>5.1f}%{flag}")

    # Category breakdown
    print(f"\n🗂  CATEGORY BREAKDOWN (last period)")
    for cat, data in list(report['category_breakdown'].items())[:8]:
        bar = '█' * int(data['percent'] / 3)
        flag = " ⚠" if data['percent'] > 30 else ""
        print(f"  {cat:<18} {data['percent']:>5.1f}%  {bar}{flag}")

    # Goal tracker
    if report['goal_tracker']:
        g = report['goal_tracker']
        print(f"\n🎯  SAVINGS GOAL")
        print(f"  Goal:        ${g['goal']:>10,.0f}")
        print(f"  Saved:       ${g['total_saved']:>10,.0f}")
        print(f"  Remaining:   ${g['remaining']:>10,.0f}")
        print(f"  Avg/month:   ${g['avg_monthly']:>10,.0f}")
        if g['months_to_goal']:
            print(f"  ETA:         {g['months_to_goal']} months")
        else:
            print(f"  ETA:         Not on track")

    # Alerts
    all_alerts = report['anomalies'] + report['stop_loss_alerts']
    if all_alerts:
        print(f"\n🚨  ALERTS ({len(all_alerts)} found)")
        for a in all_alerts:
            print(f"  → {a['message']}")
    else:
        print(f"\n✅  No alerts — all metrics within thresholds")

    print(f"\n{sep}\n")


# ─── CLI ──────────────────────────────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser(description='BudgetPulse — Personal Finance Analyzer')
    parser.add_argument('--file',   required=True,      help='Path to transactions CSV')
    parser.add_argument('--goal',   type=float, default=0, help='Savings goal amount')
    parser.add_argument('--months', type=int,   default=3,  help='Months for category breakdown')
    parser.add_argument('--export', type=str,   default='', help='Export report as JSON to this path')
    args = parser.parse_args()

    report = build_report(args.file, args.goal, args.months)
    print_report(report)

    if args.export:
        with open(args.export, 'w') as f:
            json.dump(report, f, indent=2, default=str)
        print(f"[OK] Report exported to {args.export}")


if __name__ == '__main__':
    main()
