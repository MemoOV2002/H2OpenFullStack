import { useState, useEffect } from 'react';
import { api } from '../services/api';
import {
  LineChart, Line, XAxis, YAxis, CartesianGrid,
  Tooltip, Legend, ResponsiveContainer, ReferenceLine
} from 'recharts';
import { AlertCircle } from 'lucide-react';

const TIME_RANGES = [
  { label: 'Last Hour',    value: '1' },
  { label: 'Last 6 Hours', value: '6' },
  { label: 'Last 24 Hours', value: '24' },
  { label: 'Last 7 Days',  value: '168' },
  { label: 'Last 30 Days', value: '720' },
];

export default function History() {
  const [readings, setReadings] = useState([]);
  const [loading, setLoading] = useState(true);
  const [timeRange, setTimeRange] = useState('24');

  useEffect(() => {
    loadData();
  }, [timeRange]);

  const loadData = async () => {
    setLoading(true);
    try {
      const data = await api.getReadings({ hours: parseInt(timeRange), limit: 500 });
      setReadings(data.reverse());
    } catch (error) {
      console.error('Failed to load readings:', error);
    } finally {
      setLoading(false);
    }
  };

  const chartData = readings.map((r) => ({
    time: new Date(r.timestamp).toLocaleString('en-US', {
      month: 'short', day: 'numeric', hour: '2-digit', minute: '2-digit',
    }),
    ecoli:        r.ecoli_cfu ?? null,
    turbidity:    r.turbidity ?? null,
    conductivity: r.conductivity ?? null,
    ph:           r.ph ?? null,
    temperature:  r.temperature ?? null,
  }));

  const hasTurbidity    = readings.some(r => r.turbidity != null);
  const hasConductivity = readings.some(r => r.conductivity != null);
  const hasPh           = readings.some(r => r.ph != null);
  const hasEcoli        = readings.some(r => r.ecoli_cfu != null);
  const hasTemp         = readings.some(r => r.temperature != null);

  const stats = readings.length > 0 ? {
    turbidityAvg:     avg(readings, 'turbidity'),
    turbidityMax:     max(readings, 'turbidity'),
    phAvg:            avg(readings, 'ph'),
    conductivityAvg:  avg(readings, 'conductivity'),
    safeCount:        readings.filter(r => r.is_safe).length,
    unsafeCount:      readings.filter(r => !r.is_safe).length,
  } : null;

  const tooltipStyle = {
    backgroundColor: 'white',
    border: '1px solid #e5e7eb',
    borderRadius: '8px',
    fontSize: '12px',
  };

  const xAxisProps = {
    dataKey: 'time',
    stroke: '#6b7280',
    tick: { fontSize: 11 },
    angle: -35,
    textAnchor: 'end',
    height: 70,
  };

  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-3xl font-bold text-gray-900">Historical Data</h1>
        <p className="text-gray-600 mt-1">Sensor trends for the H2Open buoy</p>
      </div>

      {/* Time Range Buttons */}
      <div className="card">
        <label className="block text-sm font-medium text-gray-700 mb-2">Time Range</label>
        <div className="flex flex-wrap gap-2">
          {TIME_RANGES.map((r) => (
            <button
              key={r.value}
              onClick={() => setTimeRange(r.value)}
              className={`px-4 py-2 rounded-lg text-sm font-medium transition-colors ${
                timeRange === r.value
                  ? 'bg-primary-600 text-white'
                  : 'bg-gray-100 text-gray-700 hover:bg-gray-200'
              }`}
            >
              {r.label}
            </button>
          ))}
        </div>
      </div>

      {/* Stats */}
      {!loading && stats && (
        <div className="grid grid-cols-2 md:grid-cols-5 gap-4">
          <StatCard title="Avg Turbidity"    value={stats.turbidityAvg}    unit="NTU"      color="blue" />
          <StatCard title="Max Turbidity"    value={stats.turbidityMax}    unit="NTU"      color="red" />
          <StatCard title="Avg pH"           value={stats.phAvg}           unit=""         color="purple" />
          <StatCard title="Safe Readings"    value={stats.safeCount}       unit="readings" color="green" />
          <StatCard title="Unsafe Readings"  value={stats.unsafeCount}     unit="readings" color="red" />
        </div>
      )}

      {loading ? (
        <div className="card text-center py-16">
          <div className="inline-block animate-spin rounded-full h-12 w-12 border-b-2 border-primary-600" />
          <p className="mt-4 text-gray-600">Loading data...</p>
        </div>
      ) : readings.length === 0 ? (
        <div className="card text-center py-16">
          <AlertCircle className="h-12 w-12 text-gray-400 mx-auto mb-4" />
          <p className="text-gray-600">No data available for this time range</p>
        </div>
      ) : (
        <div className="space-y-6">

          {hasTurbidity && (
            <div className="card">
              <h2 className="text-lg font-bold text-gray-900 mb-1">Turbidity</h2>
              <p className="text-sm text-gray-500 mb-4">Higher NTU = more suspended particles, less clarity</p>
              <ResponsiveContainer width="100%" height={280}>
                <LineChart data={chartData}>
                  <CartesianGrid strokeDasharray="3 3" stroke="#e5e7eb" />
                  <XAxis {...xAxisProps} />
                  <YAxis stroke="#6b7280" label={{ value: 'NTU', angle: -90, position: 'insideLeft', style: { fontSize: 11 } }} />
                  <Tooltip contentStyle={tooltipStyle} />
                  <Line type="monotone" dataKey="turbidity" stroke="#3b82f6" strokeWidth={2} dot={{ r: 2 }} name="Turbidity (NTU)" connectNulls />
                </LineChart>
              </ResponsiveContainer>
            </div>
          )}

          {hasConductivity && (
            <div className="card">
              <h2 className="text-lg font-bold text-gray-900 mb-1">Conductivity</h2>
              <p className="text-sm text-gray-500 mb-4">Reflects dissolved salts and ions in the water</p>
              <ResponsiveContainer width="100%" height={280}>
                <LineChart data={chartData}>
                  <CartesianGrid strokeDasharray="3 3" stroke="#e5e7eb" />
                  <XAxis {...xAxisProps} />
                  <YAxis stroke="#6b7280" label={{ value: 'μS/cm', angle: -90, position: 'insideLeft', style: { fontSize: 11 } }} />
                  <Tooltip contentStyle={tooltipStyle} />
                  <Line type="monotone" dataKey="conductivity" stroke="#8b5cf6" strokeWidth={2} dot={{ r: 2 }} name="Conductivity (μS/cm)" connectNulls />
                </LineChart>
              </ResponsiveContainer>
            </div>
          )}

          {hasPh && (
            <div className="card">
              <h2 className="text-lg font-bold text-gray-900 mb-1">pH</h2>
              <p className="text-sm text-gray-500 mb-4">Healthy freshwater range: 6.5 – 8.5</p>
              <ResponsiveContainer width="100%" height={280}>
                <LineChart data={chartData}>
                  <CartesianGrid strokeDasharray="3 3" stroke="#e5e7eb" />
                  <XAxis {...xAxisProps} />
                  <YAxis stroke="#6b7280" domain={[4, 10]} label={{ value: 'pH', angle: -90, position: 'insideLeft', style: { fontSize: 11 } }} />
                  <Tooltip contentStyle={tooltipStyle} />
                  <ReferenceLine y={6.5} stroke="#f59e0b" strokeDasharray="4 4" label={{ value: '6.5 min', fontSize: 10, fill: '#f59e0b' }} />
                  <ReferenceLine y={8.5} stroke="#f59e0b" strokeDasharray="4 4" label={{ value: '8.5 max', fontSize: 10, fill: '#f59e0b' }} />
                  <Line type="monotone" dataKey="ph" stroke="#10b981" strokeWidth={2} dot={{ r: 2 }} name="pH" connectNulls />
                </LineChart>
              </ResponsiveContainer>
            </div>
          )}

          {hasEcoli && (
            <div className="card">
              <h2 className="text-lg font-bold text-gray-900 mb-1">E. coli</h2>
              <p className="text-sm text-gray-500 mb-4">EPA recreational water safety threshold: 235 CFU/100mL</p>
              <ResponsiveContainer width="100%" height={280}>
                <LineChart data={chartData}>
                  <CartesianGrid strokeDasharray="3 3" stroke="#e5e7eb" />
                  <XAxis {...xAxisProps} />
                  <YAxis stroke="#6b7280" label={{ value: 'CFU/100mL', angle: -90, position: 'insideLeft', style: { fontSize: 11 } }} />
                  <Tooltip contentStyle={tooltipStyle} />
                  <ReferenceLine y={235} stroke="#ef4444" strokeDasharray="4 4" label={{ value: 'EPA limit', fontSize: 10, fill: '#ef4444' }} />
                  <Line type="monotone" dataKey="ecoli" stroke="#f97316" strokeWidth={2} dot={{ r: 2 }} name="E. coli (CFU/100mL)" connectNulls />
                </LineChart>
              </ResponsiveContainer>
            </div>
          )}

          {hasTemp && (
            <div className="card">
              <h2 className="text-lg font-bold text-gray-900 mb-1">Water Temperature</h2>
              <p className="text-sm text-gray-500 mb-4">Ambient water temperature over time</p>
              <ResponsiveContainer width="100%" height={280}>
                <LineChart data={chartData}>
                  <CartesianGrid strokeDasharray="3 3" stroke="#e5e7eb" />
                  <XAxis {...xAxisProps} />
                  <YAxis stroke="#6b7280" label={{ value: '°C', angle: -90, position: 'insideLeft', style: { fontSize: 11 } }} />
                  <Tooltip contentStyle={tooltipStyle} />
                  <Line type="monotone" dataKey="temperature" stroke="#06b6d4" strokeWidth={2} dot={{ r: 2 }} name="Temperature (°C)" connectNulls />
                </LineChart>
              </ResponsiveContainer>
            </div>
          )}

        </div>
      )}
    </div>
  );
}

function avg(arr, key) {
  const vals = arr.map(r => r[key]).filter(v => v != null);
  return vals.length ? (vals.reduce((a, b) => a + b, 0) / vals.length).toFixed(2) : '—';
}
function max(arr, key) {
  const vals = arr.map(r => r[key]).filter(v => v != null);
  return vals.length ? Math.max(...vals).toFixed(2) : '—';
}

function StatCard({ title, value, unit, color }) {
  const colors = {
    blue:   'bg-blue-50 border-blue-200 text-blue-700',
    green:  'bg-green-50 border-green-200 text-green-700',
    red:    'bg-red-50 border-red-200 text-red-700',
    purple: 'bg-purple-50 border-purple-200 text-purple-700',
  };
  return (
    <div className={`card border ${colors[color]}`}>
      <div className="text-sm font-medium mb-1">{title}</div>
      <div className="text-2xl font-bold">{value}</div>
      <div className="text-xs opacity-75">{unit}</div>
    </div>
  );
}