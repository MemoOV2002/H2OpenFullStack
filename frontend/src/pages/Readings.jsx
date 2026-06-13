import { useState, useEffect } from 'react';
import { api, WebSocketService } from '../services/api';
import { Droplet, Thermometer, AlertCircle, CheckCircle, RefreshCw } from 'lucide-react';

export default function Readings() {
  const [readings, setReadings] = useState([]);
  const [loading, setLoading] = useState(true);
  const [wsConnected, setWsConnected] = useState(false);

  useEffect(() => {
    loadData();

    const ws = new WebSocketService();
    ws.connect((data) => {
      if (data.type === 'sensor_reading') {
        setWsConnected(true);
        setReadings(prev => [data, ...prev].slice(0, 50));
      } else if (data.type === 'connection') {
        setWsConnected(true);
      }
    });

    return () => ws.disconnect();
  }, []);

  const loadData = async () => {
    setLoading(true);
    try {
      const data = await api.getReadings({ limit: 50 });
      setReadings(data);
    } catch (error) {
      console.error('Failed to load readings:', error);
    } finally {
      setLoading(false);
    }
  };

  const latestReading = readings[0] || null;
  const cyanoBloom = latestReading?.cyano_bloom ?? false;

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-3xl font-bold text-gray-900">Live Readings</h1>
          <p className="text-gray-600 mt-1">Real-time water quality measurements</p>
        </div>
        <div className="flex items-center gap-3">
          <div className={`flex items-center gap-2 px-3 py-1.5 rounded-full text-sm font-medium ${
            wsConnected ? 'bg-green-100 text-green-700' : 'bg-gray-100 text-gray-600'
          }`}>
            <div className={`w-2 h-2 rounded-full ${wsConnected ? 'bg-green-500 animate-pulse' : 'bg-gray-400'}`} />
            {wsConnected ? 'Live' : 'Offline'}
          </div>
          <button
            onClick={loadData}
            className="p-2 rounded-lg bg-white border border-gray-300 hover:bg-gray-50 transition-colors"
            title="Refresh data"
          >
            <RefreshCw className="h-5 w-5 text-gray-600" />
          </button>
        </div>
      </div>

      {/* Latest Reading Hero Card */}
      {!loading && latestReading && (
        <div className={`card border-l-4 ${latestReading.is_safe ? 'border-water-safe' : 'border-water-unsafe'}`}>
          <div className="flex items-center justify-between mb-4">
            <div className="flex items-center gap-2">
              <Droplet className={`h-6 w-6 ${latestReading.is_safe ? 'text-water-safe' : 'text-water-unsafe'}`} />
              <span className="text-lg font-bold text-gray-900">H2Open Buoy — Latest Reading</span>
            </div>
            {latestReading.is_safe
              ? <CheckCircle className="h-6 w-6 text-water-safe" />
              : <AlertCircle className="h-6 w-6 text-water-unsafe" />
            }
          </div>

          <div className={`rounded-lg px-4 py-3 mb-5 text-sm font-semibold ${
            latestReading.is_safe ? 'bg-green-50 text-green-800' : 'bg-red-50 text-red-800'
          }`}>
            {latestReading.is_safe
              ? '✓ Water is safe for recreation'
              : '⚠ Water is UNSAFE — Exceeds EPA threshold'}
          </div>

          <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
            {latestReading.ecoli_cfu != null && (
              <SensorStat label="E. coli" value={latestReading.ecoli_cfu?.toFixed(1)} unit="CFU/100mL" />
            )}
            {latestReading.turbidity != null && (
              <SensorStat label="Turbidity" value={latestReading.turbidity?.toFixed(2)} unit="NTU" />
            )}
            {latestReading.conductivity != null && (
              <SensorStat label="Conductivity" value={latestReading.conductivity?.toFixed(1)} unit="μS/cm" />
            )}
            {latestReading.ph != null && (
              <SensorStat label="pH" value={latestReading.ph?.toFixed(2)} unit="" />
            )}
            {latestReading.temperature != null && (
              <SensorStat label="Temperature" value={latestReading.temperature?.toFixed(1)} unit="°C" />
            )}
          </div>

          <div className="text-xs text-gray-500 mt-4 pt-4 border-t border-gray-200">
            {new Date(latestReading.timestamp).toLocaleString('en-US', {
              month: 'short', day: 'numeric', hour: '2-digit', minute: '2-digit', second: '2-digit'
            })}
          </div>
        </div>
      )}

      {/* Cyanobacteria Bloom Risk */}
      <div className={`card border-l-4 ${cyanoBloom ? 'border-water-unsafe' : 'border-blue-400'}`}>
        <div className="flex items-center justify-between mb-3">
          <div className="flex items-center gap-2">
            <span className="text-lg">🦠</span>
            <span className="text-lg font-bold text-gray-900">Cyanobacteria Bloom Risk</span>
          </div>
          {cyanoBloom
            ? <AlertCircle className="h-6 w-6 text-water-unsafe" />
            : <CheckCircle className="h-6 w-6 text-water-safe" />
          }
        </div>
        <div className={`rounded-lg px-4 py-3 text-sm font-semibold mb-2 ${
          cyanoBloom ? 'bg-red-50 text-red-800' : 'bg-green-50 text-green-800'
        }`}>
          {cyanoBloom
            ? '⚠ Bloom likely detected — Avoid contact'
            : '✓ No bloom detected — Low risk'}
        </div>
        <p className="text-xs text-gray-500">
          Binary model prediction — MA DPH threshold (70,000 cells/mL).
        </p>
      </div>

      {/* Recent Readings Table */}
      <div className="card">
        <h2 className="text-lg font-bold text-gray-900 mb-4">Recent Readings</h2>

        {loading ? (
          <div className="text-center py-12">
            <div className="inline-block animate-spin rounded-full h-12 w-12 border-b-2 border-primary-600" />
            <p className="mt-4 text-gray-600">Loading readings...</p>
          </div>
        ) : readings.length === 0 ? (
          <div className="text-center py-12">
            <AlertCircle className="h-12 w-12 text-gray-400 mx-auto mb-4" />
            <p className="text-gray-600">No readings yet</p>
          </div>
        ) : (
          <div className="overflow-x-auto">
            <table className="w-full text-sm">
              <thead>
                <tr className="border-b border-gray-200 text-left text-gray-500 text-xs uppercase tracking-wide">
                  <th className="pb-3 pr-4">Time</th>
                  <th className="pb-3 pr-4">Status</th>
                  <th className="pb-3 pr-4">Turbidity (NTU)</th>
                  <th className="pb-3 pr-4">Conductivity (μS/cm)</th>
                  <th className="pb-3 pr-4">pH</th>
                  <th className="pb-3 pr-4">E. coli (CFU/100mL)</th>
                  <th className="pb-3 pr-4">Temp (°C)</th>
                  <th className="pb-3">Cyano</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-gray-100">
                {readings.map((r, i) => (
                  <tr key={r.id || i} className="hover:bg-gray-50 transition-colors">
                    <td className="py-3 pr-4 text-gray-600 whitespace-nowrap">
                      {new Date(r.timestamp).toLocaleString('en-US', {
                        month: 'short', day: 'numeric', hour: '2-digit', minute: '2-digit'
                      })}
                    </td>
                    <td className="py-3 pr-4">
                      <span className={`inline-flex items-center gap-1 px-2 py-0.5 rounded-full text-xs font-medium ${
                        r.is_safe ? 'bg-green-100 text-green-700' : 'bg-red-100 text-red-700'
                      }`}>
                        {r.is_safe ? '✓ Safe' : '⚠ Unsafe'}
                      </span>
                    </td>
                    <td className="py-3 pr-4 text-gray-800">{r.turbidity?.toFixed(2) ?? '—'}</td>
                    <td className="py-3 pr-4 text-gray-800">{r.conductivity?.toFixed(1) ?? '—'}</td>
                    <td className="py-3 pr-4 text-gray-800">{r.ph?.toFixed(2) ?? '—'}</td>
                    <td className="py-3 pr-4 text-gray-800">{r.ecoli_cfu?.toFixed(1) ?? '—'}</td>
                    <td className="py-3 pr-4 text-gray-800">{r.temperature?.toFixed(1) ?? '—'}</td>
                    <td className="py-3">
                      <span className={`inline-flex items-center gap-1 px-2 py-0.5 rounded-full text-xs font-medium ${
                        r.cyano_bloom ? 'bg-red-100 text-red-700' : 'bg-green-100 text-green-700'
                      }`}>
                        {r.cyano_bloom ? '⚠ Bloom' : '✓ Clear'}
                      </span>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </div>
    </div>
  );
}

function SensorStat({ label, value, unit }) {
  return (
    <div className="bg-gray-50 rounded-lg p-3">
      <div className="text-xs text-gray-500 mb-1">{label}</div>
      <div className="text-xl font-bold text-gray-900">
        {value ?? '—'}
        {unit && <span className="text-xs font-normal text-gray-500 ml-1">{unit}</span>}
      </div>
    </div>
  );
}