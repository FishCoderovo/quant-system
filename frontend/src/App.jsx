import React, { useState, useEffect, useCallback } from 'react';
import {
  AreaChart, Area, XAxis, YAxis, Tooltip, ResponsiveContainer,
  BarChart, Bar, Cell, PieChart, Pie
} from 'recharts';

const API = 'http://localhost:8001';

// ─── Helpers ───
const fmt = (n, d = 2) => n != null ? Number(n).toFixed(d) : '—';
const fmtPct = (n) => n != null ? `${n >= 0 ? '+' : ''}${Number(n).toFixed(2)}%` : '—';
const cls = (...args) => args.filter(Boolean).join(' ');

const pnlColor = (v) => v > 0 ? 'var(--green)' : v < 0 ? 'var(--red)' : 'var(--text-secondary)';
const pnlBg = (v) => v > 0 ? 'var(--green-dim)' : v < 0 ? 'var(--red-dim)' : 'transparent';

// ─── Icons (inline SVG, no deps) ───
const Icon = ({ d, size = 16, color = 'currentColor' }) => (
  <svg width={size} height={size} viewBox="0 0 24 24" fill="none" stroke={color} strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
    <path d={d} />
  </svg>
);

const icons = {
  wallet: 'M21 12V7H5a2 2 0 0 1 0-4h14v4 M3 5v14a2 2 0 0 0 2 2h16v-5 M18 12a1 1 0 1 0 0 2 1 1 0 0 0 0-2z',
  chart: 'M3 3v18h18 M7 16l4-8 4 4 4-6',
  activity: 'M22 12h-4l-3 9L9 3l-3 9H2',
  layers: 'M12 2L2 7l10 5 10-5-10-5z M2 17l10 5 10-5 M2 12l10 5 10-5',
  zap: 'M13 2L3 14h9l-1 8 10-12h-9l1-8z',
  clock: 'M12 2a10 10 0 1 0 0 20 10 10 0 0 0 0-20z M12 6v6l4 2',
  target: 'M12 2a10 10 0 1 0 0 20 10 10 0 0 0 0-20z M12 8a4 4 0 1 0 0 8 4 4 0 0 0 0-8z M12 12h0',
  box: 'M21 16V8a2 2 0 0 0-1-1.73l-7-4a2 2 0 0 0-2 0l-7 4A2 2 0 0 0 3 8v8a2 2 0 0 0 1 1.73l7 4a2 2 0 0 0 2 0l7-4A2 2 0 0 0 21 16z',
  play: 'M5 3l14 9-14 9V3z',
  stop: 'M6 4h4v16H6z M14 4h4v16h-4z',
};

// ─── Custom Tooltip ───
const ChartTooltip = ({ active, payload, label }) => {
  if (!active || !payload?.length) return null;
  return (
    <div style={{
      background: '#1a1f2e', border: '1px solid #2a3040', borderRadius: 8,
      padding: '10px 14px', fontSize: 12, boxShadow: '0 8px 32px rgba(0,0,0,0.4)'
    }}>
      <div style={{ color: '#64748b', marginBottom: 4 }}>{label}</div>
      {payload.map((p, i) => (
        <div key={i} style={{ color: p.color, fontWeight: 600 }}>
          {p.name}: {typeof p.value === 'number' ? p.value.toFixed(2) : p.value}
        </div>
      ))}
    </div>
  );
};

// ─── Stat Card ───
const StatCard = ({ icon, label, value, sub, trend, delay = '' }) => (
  <div className={cls('card stat-card p-5', trend > 0 && 'positive', trend < 0 && 'negative', delay)}>
    <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start' }}>
      <div>
        <div style={{ fontSize: 12, color: 'var(--text-muted)', marginBottom: 8, display: 'flex', alignItems: 'center', gap: 6 }}>
          <Icon d={icons[icon]} size={14} color="var(--text-muted)" />
          {label}
        </div>
        <div style={{ fontSize: 26, fontWeight: 700, letterSpacing: '-0.02em', color: trend != null ? pnlColor(trend) : 'var(--text-primary)' }}>
          {value}
        </div>
        {sub && <div style={{ fontSize: 12, color: 'var(--text-secondary)', marginTop: 4 }}>{sub}</div>}
      </div>
      {trend != null && (
        <div className={cls('badge', trend >= 0 ? 'badge-green' : 'badge-red')}>
          {trend >= 0 ? '↑' : '↓'} {Math.abs(trend).toFixed(2)}%
        </div>
      )}
    </div>
  </div>
);

// ─── Strategy Badge ───
const StrategyBadge = ({ name, active }) => (
  <span style={{
    display: 'inline-block', padding: '4px 10px', borderRadius: 6, fontSize: 11, fontWeight: 500,
    background: active ? 'var(--accent-glow)' : 'rgba(255,255,255,0.04)',
    color: active ? 'var(--accent)' : 'var(--text-muted)',
    border: `1px solid ${active ? 'rgba(99,102,241,0.2)' : 'var(--border)'}`,
    marginRight: 6, marginBottom: 6
  }}>
    {name}
  </span>
);

// ─── Empty State ───
const Empty = ({ text }) => (
  <div style={{ padding: '40px 0', textAlign: 'center', color: 'var(--text-muted)', fontSize: 13 }}>
    {text}
  </div>
);

// ─── Loading Skeleton ───
const Skeleton = () => (
  <div style={{ display: 'grid', gridTemplateColumns: 'repeat(4, 1fr)', gap: 16, marginBottom: 24 }}>
    {[...Array(4)].map((_, i) => <div key={i} className="skeleton" style={{ height: 110, borderRadius: 12 }} />)}
  </div>
);

// ═══════════════════════════════════════
// Main App
// ═══════════════════════════════════════
export default function App() {
  const [data, setData] = useState(null);
  const [strategies, setStrategies] = useState(null);
  const [trades, setTrades] = useState([]);
  const [backtest, setBacktest] = useState(null);
  const [engineOn, setEngineOn] = useState(false);
  const [loading, setLoading] = useState(true);
  const [now, setNow] = useState(new Date());
  const [tab, setTab] = useState('overview');
  const [symbolConfig, setSymbolConfig] = useState({ enabled: [], available: [] });
  const [longOnly, setLongOnly] = useState(true);

  const fetchAll = useCallback(async () => {
    try {
      const [dashRes, stratRes, engRes, symRes, modeRes] = await Promise.allSettled([
        fetch(`${API}/api/dashboard`).then(r => r.json()),
        fetch(`${API}/api/strategies`).then(r => r.json()),
        fetch(`${API}/api/engine/status`).then(r => r.json()),
        fetch(`${API}/api/config/symbols`).then(r => r.json()),
        fetch(`${API}/api/config/mode`).then(r => r.json()),
      ]);
      if (dashRes.status === 'fulfilled') setData(dashRes.value);
      if (stratRes.status === 'fulfilled') setStrategies(stratRes.value);
      if (engRes.status === 'fulfilled') setEngineOn(engRes.value.is_running);
      if (symRes.status === 'fulfilled') setSymbolConfig(symRes.value);
      if (modeRes.status === 'fulfilled') setLongOnly(modeRes.value.long_only);

      // Trades
      try {
        const tRes = await fetch(`${API}/api/trades?limit=20`).then(r => r.json());
        if (Array.isArray(tRes)) setTrades(tRes);
        else if (tRes.trades) setTrades(tRes.trades);
      } catch {}

      // Backtest results (local file)
      try {
        const bRes = await fetch(`${API}/api/backtest/results`).then(r => r.json());
        setBacktest(bRes);
      } catch {}

      setLoading(false);
    } catch (e) {
      console.error(e);
      setLoading(false);
    }
  }, []);

  useEffect(() => { fetchAll(); }, [fetchAll]);
  useEffect(() => {
    const iv = setInterval(fetchAll, 8000);
    const clock = setInterval(() => setNow(new Date()), 1000);
    return () => { clearInterval(iv); clearInterval(clock); };
  }, [fetchAll]);

  const toggleEngine = async () => {
    try {
      await fetch(`${API}/api/engine/${engineOn ? 'stop' : 'start'}`, { method: 'POST' });
      setEngineOn(!engineOn);
    } catch {}
  };

  const toggleSymbol = async (symbol) => {
    const current = symbolConfig.enabled || [];
    const newList = current.includes(symbol)
      ? current.filter(s => s !== symbol)
      : [...current, symbol];
    if (newList.length === 0) return; // 至少保留一个
    try {
      const res = await fetch(`${API}/api/config/symbols?symbols=${encodeURIComponent(newList.join(','))}`, { method: 'POST' });
      const data = await res.json();
      if (data.enabled) setSymbolConfig(prev => ({ ...prev, enabled: data.enabled }));
    } catch {}
  };

  const toggleLongOnly = async () => {
    try {
      const res = await fetch(`${API}/api/config/mode?long_only=${!longOnly}`, { method: 'POST' });
      const data = await res.json();
      if (data.long_only !== undefined) setLongOnly(data.long_only);
    } catch {}
  };

  // Derive chart data from trades or positions
  const equityCurve = React.useMemo(() => {
    if (!trades?.length) return [];
    let equity = 10000;
    return trades.slice().reverse().map((t, i) => {
      equity += (t.pnl || t.profit || 0);
      return { idx: i + 1, equity: +equity.toFixed(2), time: t.time?.slice(5, 16) || `#${i + 1}` };
    });
  }, [trades]);

  // ─── Render ───
  return (
    <div style={{ minHeight: '100vh', background: 'var(--bg-primary)' }}>
      {/* ═══ Header ═══ */}
      <header style={{
        position: 'sticky', top: 0, zIndex: 50,
        background: 'rgba(11, 14, 20, 0.85)', backdropFilter: 'blur(16px)',
        borderBottom: '1px solid var(--border)',
        padding: '0 24px', height: 56,
        display: 'flex', alignItems: 'center', justifyContent: 'space-between'
      }}>
        <div style={{ display: 'flex', alignItems: 'center', gap: 12 }}>
          <div style={{ width: 28, height: 28, borderRadius: 8, background: 'var(--accent)', display: 'flex', alignItems: 'center', justifyContent: 'center' }}>
            <Icon d={icons.zap} size={14} color="white" />
          </div>
          <span style={{ fontSize: 16, fontWeight: 700, letterSpacing: '-0.01em' }}>Quant Terminal</span>
          <span style={{ fontSize: 11, color: 'var(--text-muted)', marginLeft: 4 }}>v3.1</span>
        </div>

        <div style={{ display: 'flex', alignItems: 'center', gap: 16 }}>
          {/* Clock */}
          <span style={{ fontSize: 12, color: 'var(--text-secondary)', fontFamily: 'monospace' }}>
            {now.toLocaleTimeString('zh-CN', { hour12: false })}
          </span>

          {/* Engine status */}
          <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
            <div style={{
              width: 7, height: 7, borderRadius: '50%',
              background: engineOn ? 'var(--green)' : 'var(--text-muted)',
              boxShadow: engineOn ? '0 0 8px var(--green)' : 'none',
            }} className={engineOn ? 'pulse-dot' : ''} />
            <span style={{ fontSize: 12, color: engineOn ? 'var(--green)' : 'var(--text-muted)' }}>
              {engineOn ? '运行中' : '已停止'}
            </span>
          </div>

          <button className={cls('btn', engineOn ? 'btn-danger' : 'btn-primary')} onClick={toggleEngine}>
            <Icon d={engineOn ? icons.stop : icons.play} size={13} />
            {engineOn ? '停止' : '启动'}
          </button>
        </div>
      </header>

      {/* ═══ Nav Tabs ═══ */}
      <nav style={{
        display: 'flex', gap: 0, padding: '0 24px',
        borderBottom: '1px solid var(--border)', background: 'var(--bg-primary)'
      }}>
        {[
          { id: 'overview', label: '总览', icon: 'chart' },
          { id: 'positions', label: '持仓', icon: 'target' },
          { id: 'trades', label: '交易', icon: 'activity' },
          { id: 'strategy', label: '策略', icon: 'layers' },
          { id: 'backtest', label: '回测', icon: 'box' },
          { id: 'settings', label: '设置', icon: 'layers' },
        ].map(t => (
          <button key={t.id} onClick={() => setTab(t.id)} style={{
            padding: '12px 20px', fontSize: 13, fontWeight: 500, cursor: 'pointer',
            background: 'none', border: 'none',
            color: tab === t.id ? 'var(--accent)' : 'var(--text-muted)',
            borderBottom: tab === t.id ? '2px solid var(--accent)' : '2px solid transparent',
            display: 'flex', alignItems: 'center', gap: 6, transition: 'all 0.15s'
          }}>
            <Icon d={icons[t.icon]} size={14} color={tab === t.id ? 'var(--accent)' : 'var(--text-muted)'} />
            {t.label}
          </button>
        ))}
      </nav>

      {/* ═══ Content ═══ */}
      <main style={{ padding: '24px', maxWidth: 1280, margin: '0 auto' }}>
        {loading ? <Skeleton /> : (
          <>
            {/* ─── Overview Tab ─── */}
            {tab === 'overview' && (
              <div className="fade-in">
                {/* Stat Cards */}
                <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(240px, 1fr))', gap: 16, marginBottom: 24 }}>
                  <StatCard icon="wallet" label="总资产 (USDT)" value={`$${fmt(data?.total_balance)}`} delay="fade-in" />
                  <StatCard icon="chart" label="可用资金" value={`$${fmt(data?.available_balance)}`} delay="fade-in-delay" />
                  <StatCard icon="activity" label="今日盈亏"
                    value={fmtPct(data?.daily_pnl_pct || (data?.daily_pnl ? data.daily_pnl / (data.total_balance || 1) * 100 : 0))}
                    sub={`$${fmt(data?.daily_pnl || 0)}`}
                    trend={data?.daily_pnl || 0}
                    delay="fade-in-delay" />
                  <StatCard icon="target" label="当前持仓" value={data?.positions_count || 0}
                    sub={data?.market_state || '—'} delay="fade-in-delay-2" />
                </div>

                {/* Equity Curve */}
                {equityCurve.length > 2 && (
                  <div className="card fade-in-delay" style={{ padding: '20px', marginBottom: 24 }}>
                    <div style={{ fontSize: 13, fontWeight: 600, marginBottom: 16, display: 'flex', alignItems: 'center', gap: 8 }}>
                      <Icon d={icons.chart} size={14} color="var(--accent)" />
                      权益曲线
                    </div>
                    <ResponsiveContainer width="100%" height={260}>
                      <AreaChart data={equityCurve}>
                        <defs>
                          <linearGradient id="eqGrad" x1="0" y1="0" x2="0" y2="1">
                            <stop offset="0%" stopColor="var(--accent)" stopOpacity={0.25} />
                            <stop offset="100%" stopColor="var(--accent)" stopOpacity={0} />
                          </linearGradient>
                        </defs>
                        <XAxis dataKey="time" tick={{ fontSize: 11 }} axisLine={false} tickLine={false} />
                        <YAxis tick={{ fontSize: 11 }} axisLine={false} tickLine={false} width={60}
                          domain={['auto', 'auto']} />
                        <Tooltip content={<ChartTooltip />} />
                        <Area type="monotone" dataKey="equity" name="权益" stroke="var(--accent)" fill="url(#eqGrad)"
                          strokeWidth={2} dot={false} activeDot={{ r: 4, fill: 'var(--accent)' }} />
                      </AreaChart>
                    </ResponsiveContainer>
                  </div>
                )}

                {/* Positions quick view + Strategy */}
                <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 16 }}>
                  <div className="card fade-in-delay" style={{ padding: 20 }}>
                    <div style={{ fontSize: 13, fontWeight: 600, marginBottom: 16, display: 'flex', alignItems: 'center', gap: 8 }}>
                      <Icon d={icons.target} size={14} color="var(--accent)" />
                      持仓
                    </div>
                    {data?.positions?.length ? (
                      <div style={{ display: 'flex', flexDirection: 'column', gap: 10 }}>
                        {data.positions.slice(0, 5).map((p, i) => (
                          <div key={i} style={{
                            display: 'flex', justifyContent: 'space-between', alignItems: 'center',
                            padding: '10px 12px', borderRadius: 8, background: 'rgba(255,255,255,0.02)'
                          }}>
                            <div>
                              <div style={{ fontSize: 13, fontWeight: 600 }}>{p.symbol}</div>
                              <div style={{ fontSize: 11, color: 'var(--text-muted)' }}>
                                {fmt(p.amount, 4)} @ ${fmt(p.entry_price)}
                              </div>
                            </div>
                            <div style={{ textAlign: 'right' }}>
                              <div style={{ fontSize: 13, fontWeight: 600, color: pnlColor(p.unrealized_pnl) }}>
                                {p.unrealized_pnl >= 0 ? '+' : ''}{fmt(p.unrealized_pnl)}
                              </div>
                              <div style={{ fontSize: 11, color: 'var(--text-muted)' }}>
                                SL: ${fmt(p.stop_loss)}
                              </div>
                            </div>
                          </div>
                        ))}
                      </div>
                    ) : <Empty text="暂无持仓" />}
                  </div>

                  <div className="card fade-in-delay-2" style={{ padding: 20 }}>
                    <div style={{ fontSize: 13, fontWeight: 600, marginBottom: 16, display: 'flex', alignItems: 'center', gap: 8 }}>
                      <Icon d={icons.layers} size={14} color="var(--accent)" />
                      策略状态
                    </div>
                    <div style={{ marginBottom: 12 }}>
                      <div style={{ fontSize: 11, color: 'var(--text-muted)', marginBottom: 8 }}>市场状态</div>
                      <span className="badge badge-accent" style={{ fontSize: 13 }}>
                        {data?.market_state || strategies?.market_state || '—'}
                      </span>
                    </div>
                    <div style={{ fontSize: 11, color: 'var(--text-muted)', marginBottom: 8 }}>活跃策略</div>
                    <div style={{ display: 'flex', flexWrap: 'wrap' }}>
                      {(strategies?.active_strategies || [data?.active_strategy]).filter(Boolean).map((s, i) => (
                        <StrategyBadge key={i} name={s} active />
                      ))}
                      {!(strategies?.active_strategies?.length || data?.active_strategy) && (
                        <span style={{ fontSize: 12, color: 'var(--text-muted)' }}>无活跃策略</span>
                      )}
                    </div>
                    {/* MTF Resonance */}
                    {strategies?.resonance && Object.keys(strategies.resonance).length > 0 && (
                      <div style={{ marginTop: 16 }}>
                        <div style={{ fontSize: 11, color: 'var(--text-muted)', marginBottom: 8 }}>多时间框架共振</div>
                        {Object.entries(strategies.resonance).map(([sym, r]) => (
                          <div key={sym} style={{
                            display: 'flex', justifyContent: 'space-between', alignItems: 'center',
                            padding: '6px 0', borderBottom: '1px solid var(--border)'
                          }}>
                            <span style={{ fontSize: 12 }}>{sym}</span>
                            <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
                              <div className="progress-bar" style={{ width: 60 }}>
                                <div className="progress-fill" style={{
                                  width: `${r.score}%`,
                                  background: r.tradeable ? 'var(--green)' : 'var(--yellow)'
                                }} />
                              </div>
                              <span style={{ fontSize: 11, color: r.tradeable ? 'var(--green)' : 'var(--text-muted)', minWidth: 30 }}>
                                {r.score?.toFixed(0)}
                              </span>
                            </div>
                          </div>
                        ))}
                      </div>
                    )}
                  </div>
                </div>
              </div>
            )}

            {/* ─── Positions Tab ─── */}
            {tab === 'positions' && (
              <div className="card fade-in">
                <div style={{ padding: '16px 20px', borderBottom: '1px solid var(--border)', display: 'flex', alignItems: 'center', gap: 8 }}>
                  <Icon d={icons.target} size={14} color="var(--accent)" />
                  <span style={{ fontSize: 14, fontWeight: 600 }}>当前持仓</span>
                </div>
                {data?.positions?.length ? (
                  <table className="data-table">
                    <thead>
                      <tr>
                        <th>币种</th><th style={{ textAlign: 'right' }}>数量</th>
                        <th style={{ textAlign: 'right' }}>开仓价</th><th style={{ textAlign: 'right' }}>现价</th>
                        <th style={{ textAlign: 'right' }}>未实现盈亏</th><th style={{ textAlign: 'right' }}>止损</th>
                      </tr>
                    </thead>
                    <tbody>
                      {data.positions.map((p, i) => (
                        <tr key={i}>
                          <td style={{ fontWeight: 600 }}>{p.symbol}</td>
                          <td style={{ textAlign: 'right', fontFamily: 'monospace' }}>{fmt(p.amount, 4)}</td>
                          <td style={{ textAlign: 'right', fontFamily: 'monospace' }}>${fmt(p.entry_price)}</td>
                          <td style={{ textAlign: 'right', fontFamily: 'monospace' }}>${fmt(p.current_price)}</td>
                          <td style={{ textAlign: 'right', fontWeight: 600, color: pnlColor(p.unrealized_pnl) }}>
                            {p.unrealized_pnl >= 0 ? '+' : ''}{fmt(p.unrealized_pnl)}
                          </td>
                          <td style={{ textAlign: 'right', color: 'var(--red)', fontFamily: 'monospace' }}>${fmt(p.stop_loss)}</td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                ) : <Empty text="暂无持仓" />}
              </div>
            )}

            {/* ─── Trades Tab ─── */}
            {tab === 'trades' && (
              <div className="card fade-in">
                <div style={{ padding: '16px 20px', borderBottom: '1px solid var(--border)', display: 'flex', alignItems: 'center', gap: 8 }}>
                  <Icon d={icons.activity} size={14} color="var(--accent)" />
                  <span style={{ fontSize: 14, fontWeight: 600 }}>交易记录</span>
                  <span className="badge badge-accent" style={{ marginLeft: 8 }}>{trades.length} 笔</span>
                </div>
                {trades.length ? (
                  <table className="data-table">
                    <thead>
                      <tr>
                        <th>时间</th><th>币种</th><th>方向</th>
                        <th style={{ textAlign: 'right' }}>价格</th>
                        <th style={{ textAlign: 'right' }}>数量</th>
                        <th style={{ textAlign: 'right' }}>盈亏</th>
                        <th>原因</th>
                      </tr>
                    </thead>
                    <tbody>
                      {trades.slice(0, 50).map((t, i) => (
                        <tr key={i}>
                          <td style={{ fontSize: 12, color: 'var(--text-secondary)', fontFamily: 'monospace' }}>
                            {t.time?.slice(5, 16) || '—'}
                          </td>
                          <td style={{ fontWeight: 600 }}>{t.symbol}</td>
                          <td>
                            <span className={cls('badge', t.action === 'BUY' || t.action === 'buy' ? 'badge-green' : 'badge-red')}>
                              {t.action}
                            </span>
                          </td>
                          <td style={{ textAlign: 'right', fontFamily: 'monospace' }}>${fmt(t.price)}</td>
                          <td style={{ textAlign: 'right', fontFamily: 'monospace' }}>{fmt(t.amount, 4)}</td>
                          <td style={{ textAlign: 'right', fontWeight: 600, color: pnlColor(t.pnl || t.profit) }}>
                            {t.pnl != null || t.profit != null ? `${(t.pnl || t.profit) >= 0 ? '+' : ''}${fmt(t.pnl || t.profit)}` : '—'}
                          </td>
                          <td style={{ fontSize: 12, color: 'var(--text-secondary)', maxWidth: 200, overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>
                            {t.reason || t.strategy || '—'}
                          </td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                ) : <Empty text="暂无交易记录" />}
              </div>
            )}

            {/* ─── Strategy Tab ─── */}
            {tab === 'strategy' && (
              <div className="fade-in" style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 16 }}>
                {/* Strategies list */}
                <div className="card" style={{ padding: 20 }}>
                  <div style={{ fontSize: 14, fontWeight: 600, marginBottom: 16 }}>策略列表</div>
                  {strategies?.strategies ? Object.entries(strategies.strategies).map(([name, info]) => (
                    <div key={name} style={{
                      display: 'flex', justifyContent: 'space-between', alignItems: 'center',
                      padding: '10px 0', borderBottom: '1px solid var(--border)'
                    }}>
                      <div>
                        <div style={{ fontSize: 13, fontWeight: 500 }}>{info.display_name || name}</div>
                        <div style={{ fontSize: 11, color: 'var(--text-muted)' }}>{name}</div>
                      </div>
                      <span className={cls('badge', info.enabled !== false ? 'badge-green' : 'badge-red')}>
                        {info.enabled !== false ? '启用' : '禁用'}
                      </span>
                    </div>
                  )) : <Empty text="无策略数据" />}
                </div>

                {/* Analyzers */}
                <div className="card" style={{ padding: 20 }}>
                  <div style={{ fontSize: 14, fontWeight: 600, marginBottom: 16 }}>分析器</div>
                  {strategies?.analyzers ? Object.entries(strategies.analyzers).map(([name, status]) => (
                    <div key={name} style={{
                      display: 'flex', justifyContent: 'space-between', alignItems: 'center',
                      padding: '10px 0', borderBottom: '1px solid var(--border)'
                    }}>
                      <span style={{ fontSize: 13 }}>{name}</span>
                      <span className={cls('badge', status === 'enabled' ? 'badge-green' : 'badge-red')}>
                        {status}
                      </span>
                    </div>
                  )) : <Empty text="无分析器数据" />}

                  {/* Weights */}
                  {strategies?.weights && (
                    <div style={{ marginTop: 20 }}>
                      <div style={{ fontSize: 13, fontWeight: 600, marginBottom: 12 }}>策略权重</div>
                      {Object.entries(strategies.weights).map(([name, w]) => (
                        <div key={name} style={{ marginBottom: 8 }}>
                          <div style={{ display: 'flex', justifyContent: 'space-between', fontSize: 12, marginBottom: 4 }}>
                            <span style={{ color: 'var(--text-secondary)' }}>{name}</span>
                            <span>{w}</span>
                          </div>
                          <div className="progress-bar">
                            <div className="progress-fill" style={{ width: `${w * 50}%`, background: 'var(--accent)' }} />
                          </div>
                        </div>
                      ))}
                    </div>
                  )}
                </div>
              </div>
            )}

            {/* ─── Backtest Tab ─── */}
            {tab === 'backtest' && (
              <div className="fade-in">
                <div className="card" style={{ padding: 20, marginBottom: 16 }}>
                  <div style={{ fontSize: 14, fontWeight: 600, marginBottom: 16, display: 'flex', alignItems: 'center', gap: 8 }}>
                    <Icon d={icons.box} size={14} color="var(--accent)" />
                    回测结果 — 30天 1h K线
                  </div>

                  {backtest?.results?.length ? (
                    <>
                      <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(200px, 1fr))', gap: 12, marginBottom: 20 }}>
                        {backtest.results.map((r, i) => (
                          <div key={i} className="card stat-card" style={{ padding: 16, border: '1px solid var(--border)' }}>
                            <div style={{ fontSize: 14, fontWeight: 700, marginBottom: 8 }}>{r.symbol}</div>
                            <div style={{ fontSize: 22, fontWeight: 700, color: pnlColor(r.ret), marginBottom: 4 }}>
                              {fmtPct(r.ret)}
                            </div>
                            <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 4, fontSize: 11, color: 'var(--text-secondary)' }}>
                              <span>夏普: {fmt(r.sharpe)}</span>
                              <span>回撤: {fmt(r.dd)}%</span>
                              <span>胜率: {fmt(r.wr, 1)}%</span>
                              <span>交易: {r.trades}笔</span>
                              <span>盈利因子: {fmt(r.pf)}</span>
                              <span>{r.win}赢/{r.lose}亏</span>
                            </div>
                          </div>
                        ))}
                      </div>

                      {/* Bar chart */}
                      <ResponsiveContainer width="100%" height={220}>
                        <BarChart data={backtest.results} barSize={40}>
                          <XAxis dataKey="symbol" tick={{ fontSize: 12 }} axisLine={false} tickLine={false} />
                          <YAxis tick={{ fontSize: 11 }} axisLine={false} tickLine={false} />
                          <Tooltip content={<ChartTooltip />} />
                          <Bar dataKey="ret" name="收益%" radius={[6, 6, 0, 0]}>
                            {backtest.results.map((r, i) => (
                              <Cell key={i} fill={r.ret >= 0 ? 'var(--green)' : 'var(--red)'} opacity={0.8} />
                            ))}
                          </Bar>
                        </BarChart>
                      </ResponsiveContainer>
                    </>
                  ) : <Empty text="暂无回测数据 — 运行 scripts/run_backtest.py 生成" />}
                </div>
              </div>
            )}
            {/* ─── Settings Tab ─── */}
            {tab === 'settings' && (
              <div className="fade-in" style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 16 }}>
                <div className="card" style={{ padding: 20 }}>
                  <div style={{ fontSize: 14, fontWeight: 600, marginBottom: 16 }}>币种选择</div>
                  {symbolConfig.available.map(sym => (
                    <div key={sym} style={{
                      display: 'flex', justifyContent: 'space-between', alignItems: 'center',
                      padding: '10px 0', borderBottom: '1px solid var(--border)'
                    }}>
                      <div style={{ display: 'flex', alignItems: 'center', gap: 10 }}>
                        <div style={{
                          width: 32, height: 32, borderRadius: 6,
                          background: sym.includes('BTC') ? '#F7931A' : sym.includes('ETH') ? '#627EEA' : sym.includes('SOL') ? '#14F195' : '#C2A633',
                          display: 'flex', alignItems: 'center', justifyContent: 'center',
                          fontSize: 12, fontWeight: 700, color: 'white'
                        }}>{sym.split('/')[0]}</div>
                        <span style={{ fontSize: 13 }}>{sym}</span>
                      </div>
                      <button onClick={() => toggleSymbol(sym)} style={{
                        padding: '4px 12px', borderRadius: 6, fontSize: 12,
                        background: symbolConfig.enabled.includes(sym) ? 'var(--green)' : 'var(--text-muted)',
                        border: 'none', color: 'white', cursor: 'pointer'
                      }}>{symbolConfig.enabled.includes(sym) ? '启用' : '禁用'}</button>
                    </div>
                  ))}
                  <div style={{ marginTop: 12, fontSize: 11, color: 'var(--text-muted)' }}>
                    至少保留一个币种
                  </div>
                </div>

                <div className="card" style={{ padding: 20 }}>
                  <div style={{ fontSize: 14, fontWeight: 600, marginBottom: 16 }}>运行模式</div>
                  <div style={{ padding: '10px 0', borderBottom: '1px solid var(--border)' }}>
                    <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
                      <div>
                        <div style={{ fontSize: 13, fontWeight: 500 }}>只做多 (LONG_ONLY)</div>
                        <div style={{ fontSize: 11, color: 'var(--text-muted)', marginTop: 4 }}>
                          开启：仅做多单<br/>关闭：双向交易（需要合约）
                        </div>
                      </div>
                      <button onClick={toggleLongOnly} style={{
                        padding: '4px 12px', borderRadius: 6, fontSize: 12,
                        background: longOnly ? 'var(--green)' : 'var(--red)',
                        border: 'none', color: 'white', cursor: 'pointer'
                      }}>{longOnly ? '开启' : '关闭'}</button>
                    </div>
                  </div>
                  <div style={{ marginTop: 12, fontSize: 11, color: longOnly ? 'var(--green)' : 'var(--red)' }}>
                    当前状态: {longOnly ? '只做多（保守）' : '双向交易（合约）'}
                  </div>
                </div>
              </div>
            )}
          </>
        )}
      </main>

      {/* ═══ Footer ═══ */}
      <footer style={{
        padding: '16px 24px', borderTop: '1px solid var(--border)',
        display: 'flex', justifyContent: 'space-between', fontSize: 11, color: 'var(--text-muted)'
      }}>
        <span>Quant Terminal v3.1 · Multi-Timeframe Engine</span>
        <span>API: {API}</span>
      </footer>
    </div>
  );
}
