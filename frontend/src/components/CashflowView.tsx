import { useState } from 'react'
import { formatCompact, formatCurrency, formatMonth, formatNumber, formatPercent, formatSignedPercent, humanize } from '../format'
import type { CashflowSummary, MonthlyRow } from '../types'
import { EmptyState, Skeleton } from './Badges'
import { Icon } from './Icons'
import { RefChip, RefList } from './RefChip'

interface Props {
  cashflow: CashflowSummary | null
  cashflowDone: boolean
  loading: boolean
}

export function CashflowView({ cashflow: cf, cashflowDone, loading }: Props) {
  if (loading) return <CashflowSkeleton />
  if (!cf) {
    return (
      <EmptyState
        icon="layers"
        title={cashflowDone ? 'Cashflow not available' : 'No cashflow model yet'}
        hint={
          cashflowDone
            ? 'The Cashflow stage finished but its result could not be loaded.'
            : 'Run the Cashflow stage. A deterministic Python model builds monthly inflow/outflow from the extracted transactions.'
        }
      />
    )
  }
  const cur = cf.currency
  const txCount = cf.monthly.reduce((a, m) => a + m.n_credits + m.n_debits, 0)

  return (
    <div className="cashflow">
      <section className="kpi-row kpi-row-4" aria-label="Cashflow summary">
        <Kpi label="Avg monthly inflow" value={formatCompact(cf.avg_monthly_inflow, cur)} hint={`${cf.months_covered} months`} />
        <Kpi label="Avg business inflow" value={formatCompact(cf.avg_monthly_business_inflow, cur)} hint="excl. self-transfers" />
        <Kpi label="Avg monthly net" value={formatCompact(cf.avg_monthly_net, cur)} tone={cf.avg_monthly_net >= 0 ? 'good' : 'bad'} />
        <Kpi
          label="Revenue trend"
          value={formatSignedPercent(cf.revenue_trend_pct_per_month, 1, true)}
          hint="per month"
          tone={cf.revenue_trend_pct_per_month >= 0 ? 'good' : 'bad'}
        />
        <Kpi label="Inflow volatility" value={cf.inflow_volatility_cv.toFixed(2)} hint="coefficient of variation" tone={cf.inflow_volatility_cv > 0.5 ? 'warn' : undefined} />
        <Kpi label="End-of-month share" value={formatPercent(cf.end_of_month_concentration)} hint="inflow in last 5 days" tone={cf.end_of_month_concentration > 0.5 ? 'bad' : undefined} />
        <Kpi
          label="Months covered"
          value={String(cf.months_covered)}
          hint={cf.months_missing.length > 0 ? `${cf.months_missing.length} missing` : 'none missing'}
          tone={cf.months_missing.length > 0 ? 'bad' : 'good'}
        />
        <Kpi label="Illustrative capacity" value={formatCompact(cf.suggested_capacity, cur)} hint="3 × avg net business cash" />
      </section>

      {cf.months_missing.length > 0 ? (
        <div className="callout callout-warn">
          <Icon name="alert" size={14} />
          <div className="callout-inline">
            Missing statement months:
            {cf.months_missing.map((m) => (
              <span key={m} className="chip chip-warn mono">
                {formatMonth(m)}
              </span>
            ))}
          </div>
        </div>
      ) : null}

      <section className="panel">
        <div className="panel-head">
          <h3 className="panel-title">Monthly inflow vs outflow</h3>
          <span className="muted small mono">
            {cf.period_start ?? '—'} → {cf.period_end ?? '—'}
          </span>
        </div>
        {cf.monthly.length === 0 ? (
          <p className="muted small">No monthly rows.</p>
        ) : (
          <>
            <BarChart rows={cf.monthly} currency={cur} />
            <div className="table-scroll table-sticky">
              <table className="table zebra">
                <thead>
                  <tr>
                    <th>Month</th>
                    <th className="num">Inflow</th>
                    <th className="num">Outflow</th>
                    <th className="num">Net</th>
                    <th className="num">Business inflow</th>
                    <th className="num">Credits / debits</th>
                    <th className="num">EOM share</th>
                    <th className="num">Closing</th>
                  </tr>
                </thead>
                <tbody>
                  {cf.monthly.map((m) => (
                    <tr key={m.month}>
                      <td>{formatMonth(m.month)}</td>
                      <td className="num mono">{formatCurrency(m.inflow, cur)}</td>
                      <td className="num mono">{formatCurrency(m.outflow, cur)}</td>
                      <td className={`num mono ${m.net < 0 ? 'bad' : ''}`}>{formatCurrency(m.net, cur)}</td>
                      <td className="num mono">{formatCurrency(m.business_inflow, cur)}</td>
                      <td className="num mono">
                        {m.n_credits} / {m.n_debits}
                      </td>
                      <td className={`num mono ${m.end_of_month_share > 0.5 ? 'bad' : ''}`}>{formatPercent(m.end_of_month_share, 0)}</td>
                      <td className="num mono">{m.closing_balance === null ? '—' : formatCurrency(m.closing_balance, cur)}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </>
        )}
      </section>

      <section className="panel">
        <div className="panel-head">
          <h3 className="panel-title">Source totals</h3>
          <span className="muted small">Each source counted once</span>
        </div>
        <div className="totals-grid">
          <Total label="Platform payouts (bank)" v={cf.platform_payout_total} cur={cur} />
          <Total label="Cash deposits (bank)" v={cf.cash_deposit_total} cur={cur} />
          <Total label="Dashboard gross sales" v={cf.dashboard_gross_sales_total} cur={cur} />
          <Total label="Dashboard payouts" v={cf.dashboard_payout_total} cur={cur} />
          <Total label="Receipts: purchases" v={cf.receipts_purchases_total} cur={cur} />
          <Total label="Receipts: sales" v={cf.receipts_sales_total} cur={cur} />
          <Total label="Ledger income" v={cf.ledger_income_total} cur={cur} />
          <Total label="Ledger expenses" v={cf.ledger_expense_total} cur={cur} />
          <Total label="Off-ledger income estimate" v={cf.off_ledger_income_estimate} cur={cur} />
        </div>
      </section>

      <section className="panel">
        <div className="panel-head">
          <h3 className="panel-title">
            Recurring transfers <span className="chip mono">{cf.recurring_transfers.length}</span>
          </h3>
        </div>
        {cf.recurring_transfers.length === 0 ? (
          <p className="muted small">No recurring same-day, same-amount transfers detected.</p>
        ) : (
          <div className="table-scroll table-sticky">
            <table className="table zebra">
              <thead>
                <tr>
                  <th>Counterparty</th>
                  <th className="num">Amount</th>
                  <th className="num">Day</th>
                  <th className="num">Occurrences</th>
                  <th>Months</th>
                  <th />
                  <th>Sources</th>
                </tr>
              </thead>
              <tbody>
                {cf.recurring_transfers.map((r, i) => (
                  <tr key={i}>
                    <td>{r.counterparty}</td>
                    <td className="num mono">{formatCurrency(r.amount, cur)}</td>
                    <td className="num mono">{r.day_of_month_mode}</td>
                    <td className="num mono">{r.occurrences}</td>
                    <td className="small">{r.months.map(formatMonth).join(', ')}</td>
                    <td>{r.likely_debt_service ? <span className="chip chip-bad">likely debt service</span> : null}</td>
                    <td>
                      <RefList refs={r.source_refs} label={`Recurring transfer to ${r.counterparty}`} />
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </section>

      <section className="panel">
        <div className="panel-head">
          <h3 className="panel-title">
            Flagged transactions <span className="chip mono">{cf.flagged.length}</span>
          </h3>
        </div>
        {cf.flagged.length === 0 ? (
          <p className="muted small">No self-transfers, round-trips or unusual one-offs flagged.</p>
        ) : (
          <div className="table-scroll table-sticky">
            <table className="table zebra">
              <thead>
                <tr>
                  <th>Row</th>
                  <th>Reason</th>
                  <th>Date</th>
                  <th>Description</th>
                  <th className="num">Amount</th>
                  <th>Matched</th>
                  <th>Source</th>
                </tr>
              </thead>
              <tbody>
                {cf.flagged.map((t) => (
                  <tr key={`${t.reason}-${t.row_id}`}>
                    <td className="mono">{t.row_id}</td>
                    <td>
                      <span className={`chip ${t.reason === 'self_transfer' || t.reason === 'round_trip' ? 'chip-bad' : 'chip-warn'}`}>{humanize(t.reason)}</span>
                    </td>
                    <td className="mono">{t.date}</td>
                    <td className="truncate" title={t.description}>
                      {t.description}
                    </td>
                    <td className="num mono">{formatCurrency(t.amount, cur)}</td>
                    <td className="mono">{t.matched_row_id ?? '—'}</td>
                    <td>
                      <RefChip r={t.source} label={`${humanize(t.reason)} · ${t.description}`} />
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </section>

      {cf.balance_checks.length > 0 ? (
        <section className="panel">
          <div className="panel-head">
            <h3 className="panel-title">
              Balance continuity breaks <span className="chip chip-bad mono">{cf.balance_checks.length}</span>
            </h3>
          </div>
          <div className="table-scroll table-sticky">
            <table className="table zebra">
              <thead>
                <tr>
                  <th>Row</th>
                  <th>Date</th>
                  <th className="num">Expected</th>
                  <th className="num">Reported</th>
                  <th className="num">Difference</th>
                  <th>Source</th>
                </tr>
              </thead>
              <tbody>
                {cf.balance_checks.map((b) => (
                  <tr key={b.row_id}>
                    <td className="mono">{b.row_id}</td>
                    <td className="mono">{b.date}</td>
                    <td className="num mono">{formatCurrency(b.expected_balance, cur)}</td>
                    <td className="num mono">{formatCurrency(b.reported_balance, cur)}</td>
                    <td className="num mono bad">{formatCurrency(b.difference, cur)}</td>
                    <td>
                      <RefChip r={b.source} label={`Balance break ${b.row_id}`} />
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </section>
      ) : null}

      <p className="muted small footnote">
        {cf.figures.length} catalog figure{cf.figures.length === 1 ? '' : 's'} (CF.*) available to the Analyst · {formatNumber(txCount)} transactions
      </p>
    </div>
  )
}

/** Grouped bar chart in inline SVG: inflow vs outflow per month, with axis and hover values. */
function BarChart({ rows, currency }: { rows: MonthlyRow[]; currency: string }) {
  const [hover, setHover] = useState<number | null>(null)
  const W = 640
  const H = 220
  const padL = 56
  const padR = 12
  const padT = 16
  const padB = 28
  const innerW = W - padL - padR
  const innerH = H - padT - padB
  const max = Math.max(1, ...rows.map((m) => Math.max(m.inflow, m.outflow)))
  const niceMax = niceCeil(max)
  const ticks = [0, 0.25, 0.5, 0.75, 1].map((f) => f * niceMax)
  const groupW = innerW / rows.length
  const barW = Math.min(22, groupW * 0.34)
  const gap = 3
  const y = (v: number) => padT + innerH - (v / niceMax) * innerH
  const active = hover !== null ? rows[hover] : null

  return (
    <div className="chart" onMouseLeave={() => setHover(null)}>
      <svg viewBox={`0 0 ${W} ${H}`} className="chart-svg" role="img" aria-label="Monthly inflow and outflow">
        {ticks.map((t) => (
          <g key={t}>
            <line x1={padL} x2={W - padR} y1={y(t)} y2={y(t)} className="chart-grid" />
            <text x={padL - 8} y={y(t)} className="chart-tick" textAnchor="end" dominantBaseline="middle">
              {formatCompact(t, currency).replace(/^[A-Z]{3}\s?/, '')}
            </text>
          </g>
        ))}
        {rows.map((m, i) => {
          const cx = padL + groupW * i + groupW / 2
          const isHover = hover === i
          return (
            <g key={m.month} className={`chart-group${isHover ? ' hover' : ''}`} onMouseEnter={() => setHover(i)} onFocus={() => setHover(i)} tabIndex={0}>
              <rect x={padL + groupW * i} y={padT} width={groupW} height={innerH} className="chart-hit" />
              <rect x={cx - barW - gap / 2} y={y(m.inflow)} width={barW} height={Math.max(0, padT + innerH - y(m.inflow))} className="bar-in" rx={2} />
              <rect x={cx + gap / 2} y={y(m.outflow)} width={barW} height={Math.max(0, padT + innerH - y(m.outflow))} className="bar-out" rx={2} />
              <text x={cx} y={H - 10} className="chart-label" textAnchor="middle">
                {formatMonth(m.month).slice(0, 3)}
              </text>
            </g>
          )
        })}
        <line x1={padL} x2={W - padR} y1={padT + innerH} y2={padT + innerH} className="chart-axis" />
      </svg>
      <div className="chart-footer">
        <div className="legend">
          <span>
            <i className="swatch swatch-in" /> Inflow
          </span>
          <span>
            <i className="swatch swatch-out" /> Outflow
          </span>
        </div>
        <div className="chart-readout mono" aria-live="polite">
          {active ? (
            <>
              <strong>{formatMonth(active.month)}</strong>
              <span>
                in <span className="good">{formatCurrency(active.inflow, currency)}</span>
              </span>
              <span>
                out <span className="bad">{formatCurrency(active.outflow, currency)}</span>
              </span>
              <span>net {formatCurrency(active.net, currency)}</span>
            </>
          ) : (
            <span className="muted">Hover a month for values</span>
          )}
        </div>
      </div>
    </div>
  )
}

function niceCeil(v: number): number {
  if (v <= 0) return 1
  const exp = Math.pow(10, Math.floor(Math.log10(v)))
  const n = v / exp
  const step = n <= 1 ? 1 : n <= 2 ? 2 : n <= 2.5 ? 2.5 : n <= 5 ? 5 : 10
  return step * exp
}

function Kpi({ label, value, hint, tone }: { label: string; value: string; hint?: string; tone?: 'good' | 'bad' | 'warn' }) {
  return (
    <div className={`kpi kpi-compact${tone ? ` kpi-${tone}` : ''}`}>
      <div className="kpi-label">{label}</div>
      <div className="kpi-value mono">{value}</div>
      {hint ? <div className="kpi-hint">{hint}</div> : null}
    </div>
  )
}

function Total({ label, v, cur }: { label: string; v: number; cur: string }) {
  return (
    <div className="total">
      <span className="total-label">{label}</span>
      <span className={`mono total-value${v === 0 ? ' muted' : ''}`}>{formatCurrency(v, cur)}</span>
    </div>
  )
}

function CashflowSkeleton() {
  return (
    <div className="cashflow" aria-busy="true">
      <div className="kpi-row kpi-row-4">
        {Array.from({ length: 8 }, (_, i) => (
          <div key={i} className="kpi kpi-compact">
            <Skeleton w="60%" h={10} />
            <Skeleton w="80%" h={22} className="mt-2" />
          </div>
        ))}
      </div>
      <div className="panel">
        <Skeleton w="40%" h={14} />
        <Skeleton w="100%" h={220} className="mt-3" radius={8} />
      </div>
    </div>
  )
}
