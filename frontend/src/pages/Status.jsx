import { useState, useEffect } from 'react';
import { api } from '../services/api';
import { Wifi, WifiOff, Battery, MapPin, RefreshCw, Activity } from 'lucide-react';

export default function Status() {
  const [status, setStatus] = useState(null);
  const [loading, setLoading] = useState(true);
  const [lastUpdated, setLastUpdated] = useState(null);

  useEffect(() => {
    loadStatus();
    const interval = setInterval(loadStatus, 30000);
    return () => clearInterval(interval);
  }, []);

  const loadStatus = async () => {
    try {
      const data = await api.getAllStatus();
      const buoy = Array.isArray(data) ? data[0] : data;
      setStatus(buoy || null);
      setLastUpdated(new Date());
    } catch (error) {
      console.error('Failed to load buoy status:', error);
    } finally {
      setLoading(false);
    }
  };

  const formatDate = (dateString) => {
    if (!dateString) return 'Never';
    const date = new Date(dateString);
    const diffMins = Math.floor((new Date() - date) / 60000);
    if (diffMins < 1) return 'Just now';
    if (diffMins < 60) return `${diffMins}m ago`;
    if (diffMins < 1440) return `${Math.floor(diffMins / 60)}h ago`;
    return `${Math.floor(diffMins / 1440)}d ago`;
  };

  const isOnline = status?.is_online ?? false;
  const battery  = status?.battery_level ?? null;

  const batteryColor =
    battery == null ? 'text-gray-400'
    : battery > 50  ? 'text-green-600'
    : battery > 20  ? 'text-yellow-600'
    : 'text-red-600';

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-3xl font-bold text-gray-900">Buoy Status</h1>
          <p className="text-gray-600 mt-1">Health and connectivity of the H2Open buoy</p>
        </div>
        <button
          onClick={loadStatus}
          className="p-2 rounded-lg bg-white border border-gray-300 hover:bg-gray-50 transition-colors"
          title="Refresh"
        >
          <RefreshCw className="h-5 w-5 text-gray-600" />
        </button>
      </div>

      {loading ? (
        <div className="card text-center py-16">
          <div className="inline-block animate-spin rounded-full h-12 w-12 border-b-2 border-primary-600" />
          <p className="mt-4 text-gray-600">Loading buoy status...</p>
        </div>
      ) : !status ? (
        <div className="card text-center py-16">
          <WifiOff className="h-12 w-12 text-gray-400 mx-auto mb-4" />
          <p className="text-gray-600 font-medium">No status data available</p>
          <p className="text-sm text-gray-500 mt-2">The buoy has not reported yet</p>
        </div>
      ) : (
        <div className="space-y-4">

          {/* Online/Offline Banner */}
          <div className={`card flex items-center gap-4 border-l-4 ${isOnline ? 'border-green-500' : 'border-red-400'}`}>
            <div className={`p-3 rounded-full ${isOnline ? 'bg-green-100' : 'bg-red-100'}`}>
              {isOnline
                ? <Wifi className="h-7 w-7 text-green-600" />
                : <WifiOff className="h-7 w-7 text-red-500" />
              }
            </div>
            <div>
              <div className="text-lg font-bold text-gray-900">
                H2Open Buoy
                <span className={`ml-3 text-sm font-medium px-2 py-0.5 rounded-full ${
                  isOnline ? 'bg-green-100 text-green-700' : 'bg-red-100 text-red-700'
                }`}>
                  {isOnline ? 'Online' : 'Offline'}
                </span>
              </div>
              <div className="text-sm text-gray-500">Last contact: {formatDate(status.last_heartbeat)}</div>
            </div>
          </div>

          {/* Detail Cards */}
          <div className="grid grid-cols-1 md:grid-cols-3 gap-4">

            {/* Battery */}
            <div className="card">
              <div className="flex items-center gap-2 text-gray-500 text-sm mb-2">
                <Battery className="h-4 w-4" />
                Battery Level
              </div>
              {battery != null ? (
                <div>
                  <div className={`text-3xl font-bold ${batteryColor}`}>{battery}%</div>
                  <div className="mt-3 h-2 bg-gray-200 rounded-full overflow-hidden">
                    <div
                      className={`h-2 rounded-full transition-all ${
                        battery > 50 ? 'bg-green-500' : battery > 20 ? 'bg-yellow-500' : 'bg-red-500'
                      }`}
                      style={{ width: `${battery}%` }}
                    />
                  </div>
                  {battery <= 20 && (
                    <p className="text-xs text-red-600 mt-2 font-medium">Low battery - recharge soon</p>
                  )}
                </div>
              ) : (
                <div className="text-gray-400 text-sm mt-2">Not available</div>
              )}
            </div>

            {/* Location */}
            <div className="card">
              <div className="flex items-center gap-2 text-gray-500 text-sm mb-2">
                <MapPin className="h-4 w-4" />
                Location
              </div>
              {status.latitude && status.longitude ? (
                <div>
                  {status.location_name && (
                    <div className="text-sm font-medium text-gray-800 mb-1">{status.location_name}</div>
                  )}
                  <div className="text-sm font-mono text-gray-600">
                    {status.latitude.toFixed(5)}, {status.longitude.toFixed(5)}
                  </div>
                  
                  <a href={`https://www.google.com/maps?q=${status.latitude},${status.longitude}`}
                    target="_blank"
                    rel="noopener noreferrer"
                    className="inline-block mt-3 text-xs text-primary-600 hover:underline"
                  >
                    Open in Google Maps
                  </a>
                </div>
              ) : (
                <div className="text-gray-400 text-sm mt-2">Location not available</div>
              )}
            </div>

            {/* Latest Reading */}
            <div className="card">
              <div className="flex items-center gap-2 text-gray-500 text-sm mb-2">
                <Activity className="h-4 w-4" />
                Latest Reading
              </div>
              {status.last_ecoli_cfu != null ? (
                <div>
                  <div className="text-3xl font-bold text-gray-800">
                    {status.last_ecoli_cfu.toFixed(1)}
                    <span className="text-sm font-normal text-gray-500 ml-1">CFU/100mL</span>
                  </div>
                  <div className={`text-sm font-medium mt-1 ${status.is_safe ? 'text-green-600' : 'text-red-600'}`}>
                    {status.is_safe ? 'Safe' : 'Unsafe'}
                  </div>
                </div>
              ) : (
                <div className="text-gray-400 text-sm mt-2">No reading yet</div>
              )}
            </div>

          </div>
        </div>
      )}

      {lastUpdated && (
        <p className="text-xs text-gray-400 text-right">
          Refreshed at {lastUpdated.toLocaleTimeString()} · auto-updates every 30s
        </p>
      )}
    </div>
  );
}