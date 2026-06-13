# H2Open Backend - Quick Start Guide

## Installation (5 minutes)

### Step 1: Install PostgreSQL

**macOS:**
```bash
brew install postgresql@15
brew services start postgresql@15
```

**Windows:** Download installer from postgresql.org

**Linux:**
```bash
sudo apt install postgresql postgresql-contrib
sudo systemctl start postgresql
```

### Step 2: Create Database
```bash
# Open PostgreSQL
psql postgres

# Run these commands:
CREATE DATABASE h2open_db;
CREATE USER h2open_user WITH PASSWORD 'h2open_password';
GRANT ALL PRIVILEGES ON DATABASE h2open_db TO h2open_user;
\q
```

### Step 3: Set Up Python Project
```bash
# Navigate to project directory
cd h2open-backend

# Create virtual environment
python3 -m venv venv

# Activate it
source venv/bin/activate  # Mac/Linux
# OR
venv\Scripts\activate  # Windows

# Install dependencies
pip install -r requirements.txt

# Create .env file
cp .env.example .env
# (No need to edit if using default credentials)
```

### Step 4: Run the Server
```bash
python main.py
```

✅ Server running at http://localhost:8000

## Test It Works

### Option 1: Interactive Docs
Open http://localhost:8000/docs in your browser

### Option 2: Run Test Script
```bash
# In a new terminal (keep server running)
cd h2open-backend
source venv/bin/activate
python test_api.py
```

### Option 3: Manual Test
```bash
# Create a reading
curl -X POST "http://localhost:8000/api/v1/readings" \
  -H "Content-Type: application/json" \
  -d '{"buoy_id": "buoy_001", "ecoli_cfu": 180.5}'

# Get readings
curl "http://localhost:8000/api/v1/readings"
```

### Option 4: Test WebSocket
Open `test_websocket.html` in your browser and click "Connect"

## Key Endpoints

- **API Docs:** http://localhost:8000/docs
- **Health:** http://localhost:8000/health
- **Create Reading:** POST /api/v1/readings
- **Get Readings:** GET /api/v1/readings
- **Check Safety:** GET /api/v1/safety/{buoy_id}
- **WebSocket:** ws://localhost:8000/ws/live-data

## Next Steps

1. ✅ API is running
2. Test endpoints with sample data
3. Integrate with your LoRa code
4. Build React frontend
5. Deploy to production

## Common Issues

**"Can't connect to database"**
- Check PostgreSQL is running: `brew services list`
- Verify credentials in `.env` match database setup

**"Port 8000 already in use"**
- Change port in main.py: `uvicorn.run(..., port=8001)`

**"Module not found"**
- Make sure virtual environment is activated
- Run `pip install -r requirements.txt` again

## Project Structure
```
h2open-backend/
├── main.py              # Start server here
├── requirements.txt     # Dependencies
├── .env.example        # Config template
├── test_api.py         # Test script
├── test_websocket.html # WebSocket test
└── app/
    ├── database.py     # DB config
    ├── models.py       # Data models
    ├── schemas.py      # Validation
    └── routers/        # API endpoints
```

## Development Workflow

1. Make sure PostgreSQL is running
2. Activate virtual environment: `source venv/bin/activate`
3. Start server: `python main.py`
4. Server auto-reloads when you edit code
5. Test changes with http://localhost:8000/docs

**Happy coding! 🚀**
