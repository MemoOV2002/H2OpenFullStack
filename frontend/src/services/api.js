// API service for communicating with FastAPI backend

const isSecure = window.location.protocol === 'https:';
const BASE_HOST = 'localhost:8000';
const API_BASE_URL = `${isSecure ? 'https' : 'http'}://${BASE_HOST}/api/v1`;

export const api = {
  // Get all readings with optional filters
  async getReadings(params = {}) {
    const queryParams = new URLSearchParams();
    if (params.buoy_id) queryParams.append('buoy_id', params.buoy_id);
    if (params.limit) queryParams.append('limit', params.limit);
    if (params.hours) queryParams.append('hours', params.hours);
    
    const url = `${API_BASE_URL}/readings?${queryParams}`;
    const response = await fetch(url);
    if (!response.ok) throw new Error('Failed to fetch readings');
    return response.json();
  },

  // Get latest reading for a buoy
  async getLatestReading(buoyId) {
    const response = await fetch(`${API_BASE_URL}/readings/latest/${buoyId}`);
    if (!response.ok) throw new Error('Failed to fetch latest reading');
    return response.json();
  },

  // Check water safety for a buoy
  async checkSafety(buoyId) {
    const response = await fetch(`${API_BASE_URL}/safety/${buoyId}`);
    if (!response.ok) throw new Error('Failed to check safety');
    return response.json();
  },

  // Get all buoy statuses
  async getAllStatus() {
    const response = await fetch(`${API_BASE_URL}/status`);
    if (!response.ok) throw new Error('Failed to fetch statuses');
    return response.json();
  },

  // Get specific buoy status
  async getBuoyStatus(buoyId) {
    const response = await fetch(`${API_BASE_URL}/status/${buoyId}`);
    if (!response.ok) throw new Error('Failed to fetch buoy status');
    return response.json();
  },

  // Get all buoy IDs
  async getBuoyIds() {
    const response = await fetch(`${API_BASE_URL}/buoys`);
    if (!response.ok) throw new Error('Failed to fetch buoy IDs');
    return response.json();
  },

  // Create new reading (for testing)
  async createReading(data) {
    const response = await fetch(`${API_BASE_URL}/readings`, {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
      },
      body: JSON.stringify(data),
    });
    if (!response.ok) throw new Error('Failed to create reading');
    return response.json();
  },
};

// WebSocket connection for real-time updates
export class WebSocketService {
  constructor() {
    this.ws = null;
    this.listeners = [];
    this._onMessage = null;
    this._reconnectTimer = null;
  }

  connect(onMessage) {
    // Prevent double connection (React StrictMode mounts twice in development)
    if (this.ws && (this.ws.readyState === WebSocket.CONNECTING || 
                    this.ws.readyState === WebSocket.OPEN)) {
      return;
    }

    // Store callback so reconnect uses the same one
    this._onMessage = onMessage;

    this.ws = new WebSocket(`${isSecure ? 'wss' : 'ws'}://${BASE_HOST}/ws/live-data`);
    
    this.ws.onopen = () => {
      console.log('✅ WebSocket connected');
      // Clear any pending reconnect timer
      if (this._reconnectTimer) {
        clearTimeout(this._reconnectTimer);
        this._reconnectTimer = null;
      }
    };
    
    this.ws.onmessage = (event) => {
      const data = JSON.parse(event.data);
      if (this._onMessage) this._onMessage(data);
      this.listeners.forEach(listener => listener(data));
    };
    
    this.ws.onerror = (error) => {
      console.error('❌ WebSocket error:', error);
    };
    
    this.ws.onclose = () => {
      console.log('WebSocket disconnected');
      this.ws = null;
      // Auto-reconnect after 3 seconds
      this._reconnectTimer = setTimeout(() => this.connect(this._onMessage), 3000);
    };
  }

  addListener(callback) {
    this.listeners.push(callback);
  }

  removeListener(callback) {
    this.listeners = this.listeners.filter(l => l !== callback);
  }

  disconnect() {
    if (this._reconnectTimer) {
      clearTimeout(this._reconnectTimer);
      this._reconnectTimer = null;
    }
    if (this.ws) {
      this.ws.onclose = null;  // prevent reconnect on intentional disconnect
      this.ws.close();
      this.ws = null;
    }
  }
}