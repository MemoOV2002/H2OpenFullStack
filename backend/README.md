# H2Open Backend API

Water quality monitoring system for Charles River - FastAPI Backend

## Project Structure

```
h2open-backend/
├── main.py                 # FastAPI application entry point
├── requirements.txt        # Python dependencies
├── .env.example           # Environment variables template
├── app/
│   ├── __init__.py
│   ├── database.py        # Database configuration
│   ├── models.py          # SQLAlchemy models
│   ├── schemas.py         # Pydantic schemas
│   └── routers/
│       ├── __init__.py
│       ├── readings.py    # Sensor reading endpoints
│       ├── status.py      # Buoy status endpoints
│       └── websocket.py   # WebSocket for real-time data
```

## Setup Instructions

### 1. Install PostgreSQL

**macOS (using Homebrew):**
```bash
brew install postgresql@15
brew services start postgresql@15
```

**Windows:**
Download and install from: https://www.postgresql.org/download/windows/

**Linux (Ubuntu/Debian):**
```bash
sudo apt update
sudo apt install postgresql postgresql-contrib
sudo systemctl start postgresql
```

### 2. Create Database

```bash
# Connect to PostgreSQL
psql postgres

# Create database and user
CREATE DATABASE h2open_db;
CREATE USER h2open_user WITH PASSWORD 'h2open_password';
GRANT ALL PRIVILEGES ON DATABASE h2open_db TO h2open_user;

# Exit PostgreSQL
\q
```

### 3. Install TimescaleDB (Optional but Recommended)

TimescaleDB is a PostgreSQL extension optimized for time-series data.

**macOS:**
```bash
brew tap timescale/tap
brew install timescaledb
timescaledb-tune --quiet --yes
```

**Linux:**
```bash
sudo add-apt-repository ppa:timescale/timescaledb-ppa
sudo apt update
sudo apt install timescaledb-postgresql-15
sudo timescaledb-tune --quiet --yes
```

**Enable TimescaleDB in your database:**
```bash
psql -U h2open_user -d h2open_db
CREATE EXTENSION IF NOT EXISTS timescaledb;
\q
```

### 4. Set Up Python Environment

```bash
# Create virtual environment
python3 -m venv venv

# Activate virtual environment
# On macOS/Linux:
source venv/bin/activate
# On Windows:
venv\Scripts\activate

# Install dependencies
pip install -r requirements.txt
```

### 5. Configure Environment Variables

```bash
# Copy example env file
cp .env.example .env

# Edit .env with your database credentials
# (use the ones you created in step 2)
```

### 6. Run the Application

```bash
# Make sure you're in the h2open-backend directory
# and virtual environment is activated

python main.py
```

The API will be available at:
- **API:** http://localhost:8000
- **API Docs:** http://localhost:8000/docs
- **WebSocket:** ws://localhost:8000/ws/live-data

## Testing the API

### Using the Interactive Docs

1. Open http://localhost:8000/docs in your browser
2. Click on any endpoint to expand it
3. Click "Try it out"
4. Fill in the parameters
5. Click "Execute"

### Using curl

**Create a sensor reading:**
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

**Get all readings:**
```bash
curl "http://localhost:8000/api/v1/readings"
```

**Get readings for specific buoy:**
```bash
curl "http://localhost:8000/api/v1/readings?buoy_id=buoy_001"
```

**Check water safety:**
```bash
curl "http://localhost:8000/api/v1/safety/buoy_001"
```

**Get buoy status:**
```bash
curl "http://localhost:8000/api/v1/status/buoy_001"
```

### Testing WebSocket

You can test WebSocket using a tool like:
- **Browser Console** (see test_websocket.html below)
- **Postman** (supports WebSocket)
- **wscat:** `npm install -g wscat && wscat -c ws://localhost:8000/ws/live-data`

## API Endpoints

### Readings
- `POST /api/v1/readings` - Create new sensor reading
- `GET /api/v1/readings` - Get readings (with filters)
- `GET /api/v1/readings/{id}` - Get specific reading
- `GET /api/v1/readings/latest/{buoy_id}` - Get latest reading for buoy
- `GET /api/v1/safety/{buoy_id}` - Check water safety

### Status
- `GET /api/v1/status` - Get all buoy statuses
- `GET /api/v1/status/{buoy_id}` - Get specific buoy status
- `GET /api/v1/buoys` - Get list of all buoy IDs

### WebSocket
- `WS /ws/live-data` - Real-time sensor data stream

## Database Models

### SensorReading
- Water quality measurements from buoys
- Stores E. coli, temperature, pH, turbidity, DO
- Automatic safety assessment (EPA threshold: 235 CFU/100mL)

### BuoyStatus
- Current status of each buoy
- Last reading, online status, battery level
- Location and metadata

## Next Steps

1. ✅ Backend API is running
2. 🔄 Test endpoints with sample data
3. 📊 Connect your LoRa code to POST readings
4. 🌐 Build React frontend (next phase)
5. 🚀 Deploy to production server

## Troubleshooting

**Database connection error:**
- Make sure PostgreSQL is running: `brew services list` or `sudo systemctl status postgresql`
- Check credentials in `.env` file
- Verify database exists: `psql -U h2open_user -d h2open_db`

**Port already in use:**
- Change port in `main.py`: `uvicorn.run("main:app", port=8001)`

**Import errors:**
- Make sure virtual environment is activated
- Reinstall dependencies: `pip install -r requirements.txt`

## Contact

Questions? Ask Memo or Guillermo!
