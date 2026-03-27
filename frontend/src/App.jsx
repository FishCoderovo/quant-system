import React, { useState, useEffect } from 'react';
import { LineChart, Line, XAxis, YAxis, CartesianGrid, Tooltip, ResponsiveContainer } from 'recharts';

function App() {
  const [dashboard, setDashboard] = useState(null);
  const [loading, setLoading] = useState(true);
  const [engineStatus, setEngineStatus] = useState(false);

  const API_URL = 'http://localhost:8001';

  useEffect(() => {
    fetchDashboard();
    fetchEngineStatus();
    const interval = setInterval(() => {
      fetchDashboard();
      fetchEngineStatus();
    }, 5000);
    return () => clearInterval(interval);
  }, []);

  const fetchDashboard = async () => {
    try {
      const res = await fetch(`${API_URL}/api/dashboard`);
      const data = await res.json();
      setDashboard(data);
      setLoading(false);
    } catch (e) {
      console.error('获取数据失败:', e);
    }
  };

  const fetchEngineStatus = async () => {
    try {
      const res = await fetch(`${API_URL}/api/engine/status`);
      const data = await res.json();
      setEngineStatus(data.is_running);
    } catch (e) {
      console.error('获取引擎状态失败:', e);
    }
  };

  const toggleEngine = async () => {
    const endpoint = engineStatus ? '/api/engine/stop' : '/api/engine/start';
    try {
      await fetch(`${API_URL}${endpoint}`, { method: 'POST' });
      fetchEngineStatus();
    } catch (e) {
      console.error('切换引擎失败:', e);
    }
  };

  if (loading) return <div className="p-8">加载中...</div>;

  return (
    <div className="min-h-screen bg-gray-100">
      {/* Header */}
      <header className="bg-white shadow">
        <div className="max-w-7xl mx-auto px-4 py-4 flex justify-between items-center">
          <h1 className="text-2xl font-bold text-gray-900">Quant System</h1>
          <div className="flex items-center gap-4">
            <span className={`px-3 py-1 rounded-full text-sm ${
              engineStatus ? 'bg-green-100 text-green-800' : 'bg-gray-100 text-gray-800'
            }`}>
              {engineStatus ? '运行中' : '已停止'}
            </span>
            <button
              onClick={toggleEngine}
              className={`px-4 py-2 rounded text-white ${
                engineStatus ? 'bg-red-500 hover:bg-red-600' : 'bg-green-500 hover:bg-green-600'
              }`}
            >
              {engineStatus ? '停止引擎' : '启动引擎'}
            </button>
          </div>
        </div>
      </header>

      <main className="max-w-7xl mx-auto px-4 py-6">
        {/* 资产概览 */}
        <div className="grid grid-cols-1 md:grid-cols-4 gap-4 mb-6">
          <div className="bg-white rounded-lg shadow p-4">
            <p className="text-sm text-gray-500">总资产</p>
            <p className="text-2xl font-bold">${dashboard?.total_balance?.toFixed(2) || '0.00'}</p>
          </div>
          <div className="bg-white rounded-lg shadow p-4">
            <p className="text-sm text-gray-500">可用资金</p>
            <p className="text-2xl font-bold">${dashboard?.available_balance?.toFixed(2) || '0.00'}</p>
          </div>
          <div className="bg-white rounded-lg shadow p-4">
            <p className="text-sm text-gray-500">今日盈亏</p>
            <p className={`text-2xl font-bold ${(dashboard?.daily_pnl || 0) >= 0 ? 'text-green-600' : 'text-red-600'}`}>
              {dashboard?.daily_pnl >= 0 ? '+' : ''}{dashboard?.daily_pnl?.toFixed(2) || '0.00'}
            </p>
          </div>
          <div className="bg-white rounded-lg shadow p-4">
            <p className="text-sm text-gray-500">当前持仓</p>
            <p className="text-2xl font-bold">{dashboard?.positions_count || 0}</p>
          </div>
        </div>

        {/* 市场状态和策略 */}
        <div className="grid grid-cols-1 md:grid-cols-2 gap-4 mb-6">
          <div className="bg-white rounded-lg shadow p-4">
            <h2 className="text-lg font-semibold mb-2">市场状态</h2>
            <p className="text-gray-700">{dashboard?.market_state || 'unknown'}</p>
          </div>
          <div className="bg-white rounded-lg shadow p-4">
            <h2 className="text-lg font-semibold mb-2">活跃策略</h2>
            <p className="text-gray-700">{dashboard?.active_strategy || 'None'}</p>
          </div>
        </div>

        {/* 持仓列表 */}
        <div className="bg-white rounded-lg shadow mb-6">
          <div className="px-4 py-3 border-b">
            <h2 className="text-lg font-semibold">当前持仓</h2>
          </div>
          <div className="overflow-x-auto">
            <table className="w-full">
              <thead className="bg-gray-50">
                <tr>
                  <th className="px-4 py-2 text-left text-xs font-medium text-gray-500">币种</th>
                  <th className="px-4 py-2 text-right text-xs font-medium text-gray-500">数量</th>
                  <th className="px-4 py-2 text-right text-xs font-medium text-gray-500">开仓价</th>
                  <th className="px-4 py-2 text-right text-xs font-medium text-gray-500">当前价</th>
                  <th className="px-4 py-2 text-right text-xs font-medium text-gray-500">未实现盈亏</th>
                  <th className="px-4 py-2 text-right text-xs font-medium text-gray-500">止损价</th>
                </tr>
              </thead>
              <tbody>
                {dashboard?.positions?.map((pos) => (
                  <tr key={pos.id} className="border-t">
                    <td className="px-4 py-3">{pos.symbol}</td>
                    <td className="px-4 py-3 text-right">{pos.amount?.toFixed(4)}</td>
                    <td className="px-4 py-3 text-right">${pos.entry_price?.toFixed(2)}</td>
                    <td className="px-4 py-3 text-right">${pos.current_price?.toFixed(2)}</td>
                    <td className={`px-4 py-3 text-right ${(pos.unrealized_pnl || 0) >= 0 ? 'text-green-600' : 'text-red-600'}`}>
                      {pos.unrealized_pnl >= 0 ? '+' : ''}{pos.unrealized_pnl?.toFixed(2)}
                    </td>
                    <td className="px-4 py-3 text-right text-red-500">${pos.stop_loss?.toFixed(2)}</td>
                  </tr>
                ))}
                {(!dashboard?.positions || dashboard.positions.length === 0) && (
                  <tr>
                    <td colSpan={6} className="px-4 py-8 text-center text-gray-500">暂无持仓</td>
                  </tr>
                )}
              </tbody>
            </table>
          </div>
        </div>
      </main>
    </div>
  );
}

export default App;
