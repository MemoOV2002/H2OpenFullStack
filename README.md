# H2Open Water Quality Monitoring System

Full-stack application for monitoring water quality in the Charles River using LoRa-enabled sensor buoys.

**Team 08** | Lead Engineer: Guillermo Ortega | Backend Developer: Memo Ortega

## Project Overview

H2Open provides real-time water quality monitoring with E. coli measurements, environmental sensors, and public-facing dashboard. The system evaluates water safety against EPA thresholds (235 CFU/100mL) and provides instant safety decisions to stakeholders.

## Technology Stack

**Backend:**
- FastAPI (Python web framework)
- PostgreSQL + TimescaleDB (time-series database)
- SQLAlchemy ORM
- WebSocket for real-time updates
- Pydantic for data validation

**Frontend:**
- React 18
- Tailwind CSS
- React Router
- Recharts (data visualization)
- Vite (development server)

**Communication:**
- LoRa wireless protocol
- T-Beam devices for sensor nodes
- RESTful API
- WebSocket streaming

## Project Structure

```
h2open-project/
├── backend/                    # FastAPI backend
│   ├── app/
│   │   ├── routers/           # API endpoints
│   │   ├── models.py          # Database models
│   │   ├── schemas.py         # Pydantic schemas
│   │   └── database.py        # DB configuration
│   ├── main.py                # FastAPI app entry
│   ├── requirements.txt       # Python dependencies
│   └── README.md              # Backend docs
│
├── frontend/                   # React frontend
│   ├── src/
│   │   ├── components/        # UI components
│   │   ├── pages/             # Page components
│   │   └── services/          # API client
│   ├── package.json           # Node dependencies
│   └── README.md              # Frontend docs
│
└── README.md                   # This file
```

## Quick Start

### Prerequisites
- Python 3.9+
- Node.js 18+
- PostgreSQL 15+

### 1. Backend Setup

```bash
cd backend

# Create virtual environment
python3 -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate

# Install dependencies
pip install -r requirements.txt

# Set up PostgreSQL database
psql postgres
CREATE DATABASE h2open_db;
CREATE USER h2open_user WITH PASSWORD 'h2open_password';
GRANT ALL PRIVILEGES ON DATABASE h2open_db TO h2open_user;
\q

# Grant schema permissions (PostgreSQL 15)
psql -d h2open_db
GRANT ALL ON SCHEMA public TO h2open_user;
GRANT USAGE ON SCHEMA public TO h2open_user;
\q

# Configure environment
cp .env.example .env
# Edit .env with your database credentials

# Run backend
python main.py
```

Backend runs at **http://localhost:8000**

API Docs: **http://localhost:8000/docs**

### 2. Frontend Setup

```bash
cd frontend

# Install dependencies
npm install

# Start development server
npm run dev
```

Frontend runs at **http://localhost:5173**

## Development Workflow

**Terminal 1 - Backend:**
```bash
cd backend
source venv/bin/activate
python main.py
```

**Terminal 2 - Frontend:**
```bash
cd frontend
npm run dev
```

**Terminal 3 - Testing/Commands:**
```bash
# Add test data
cd backend
python test_api.py

# Or use API docs
open http://localhost:8000/docs
```

## Features

### Backend API

**Endpoints:**
- `POST /api/v1/readings` - Ingest sensor data
- `GET /api/v1/readings` - Query readings (with filters)
- `GET /api/v1/safety/{buoy_id}` - Check water safety
- `GET /api/v1/status` - Buoy health status
- `WS /ws/live-data` - Real-time data stream

**Database Models:**
- `SensorReading` - E. coli measurements, environmental data
- `BuoyStatus` - Buoy health, battery, location

**Security:**
- User isolation with restricted PostgreSQL privileges
- CORS configuration for frontend access
- Input validation via Pydantic schemas

### Frontend Dashboard

**Pages:**
- **Readings** - Live sensor data with real-time updates
- **Status** - Buoy health monitoring (online/offline, battery)
- **History** - Interactive charts and trends

**Features:**
- Responsive design (mobile + desktop)
- WebSocket live updates
- Filter by buoy and time range
- Color-coded safety indicators
- Battery level monitoring
- Historical data visualization

## Testing

### Backend Tests
```bash
cd backend
source venv/bin/activate
python test_api.py
```

### Frontend Testing
```bash
cd frontend
npm run dev
```

Open http://localhost:5173 and interact with the UI

### WebSocket Test
Open `backend/test_websocket.html` in your browser

## API Usage Examples

### Create a Reading
```bash
curl -X POST "http://localhost:8000/api/v1/readings" \
  -H "Content-Type: application/json" \
  -d '{
    "buoy_id": "buoy_001",
    "ecoli_cfu": 180.5,
    "temperature": 22.3,
    "latitude": 42.3601,
    "longitude": -71.0942
  }'
```

### Get Latest Reading
```bash
curl "http://localhost:8000/api/v1/readings/latest/buoy_001"
```

### Check Water Safety
```bash
curl "http://localhost:8000/api/v1/safety/buoy_001"
```

## Deployment

### Development (Current)
- Backend: http://localhost:8000
- Frontend: http://localhost:5173

### Production (Future)
- Backend: Deploy FastAPI with Uvicorn + NGINX
- Frontend: Build with `npm run build`, serve static files
- Database: PostgreSQL with TimescaleDB extension
- SSL: Let's Encrypt certificates

## Database Schema

### SensorReading Table
- `id` (PK) - Unique reading identifier
- `buoy_id` (indexed) - Buoy identifier
- `timestamp` (indexed) - Measurement time
- `ecoli_cfu` - E. coli count (CFU/100mL)
- `is_safe` - Boolean (true if < 235 CFU/100mL)
- `temperature`, `ph`, `turbidity`, `dissolved_oxygen` - Environmental data
- `latitude`, `longitude` - Location

### BuoyStatus Table
- `buoy_id` (PK) - Unique buoy identifier
- `is_online` - Connection status
- `battery_level` - Battery percentage
- `last_heartbeat` - Last contact time
- `latitude`, `longitude`, `location_name` - Position

## LoRa Integration

**Current Status:** Backend API ready for integration

**Next Steps:**
1. LoRa receiver code sends POST requests to `/api/v1/readings`
2. Backend automatically:
   - Validates data
   - Evaluates safety
   - Stores in database
   - Broadcasts via WebSocket
   - Updates buoy status

**Integration Example:**
```python
import requests

# When LoRa data arrives
requests.post("http://localhost:8000/api/v1/readings", json={
    "buoy_id": "buoy_001",
    "ecoli_cfu": measured_value,
    "temperature": temp_value
})
```

## Troubleshooting

**Backend won't start:**
- Check PostgreSQL is running: `brew services list`
- Verify database credentials in `.env`
- Check port 8000 isn't in use

**Frontend won't connect:**
- Ensure backend is running at http://localhost:8000
- Check browser console for CORS errors
- Verify API URLs in `frontend/src/services/api.js`

**Database permission errors:**
- Run schema grants (see Backend Setup step 3)
- Verify user has privileges: `\du` in psql

## Project Timeline

- ✅ Week [XX]: Backend architecture and database design
- ✅ Week [XX]: FastAPI implementation and PostgreSQL setup
- ✅ Week [XX]: Frontend dashboard with Tailwind CSS
- 🔄 Week [XX]: LoRa integration with backend API
- 📅 Future: Production deployment and monitoring

## Documentation

- **Backend Details:** See `backend/README.md`
- **Frontend Details:** See `frontend/README.md`
- **API Documentation:** http://localhost:8000/docs (when running)

## Team

H2Open - Team 08
- Lead Engineer: Guillermo Ortega
- Backend Developer: Memo Ortega

## License

Educational project for water quality monitoring coursework.
