# H2Open Complete Setup Guide

Get the full-stack H2Open system running in 15 minutes.

## Overview

This project has two parts that work together:
- **Backend** (FastAPI + PostgreSQL) - Handles data, WebSocket, API
- **Frontend** (React + Tailwind) - User interface, dashboard

Both run simultaneously during development.

## Prerequisites

Install these first:

1. **Python 3.9+** 
   - Check: `python3 --version`
   - Download: https://www.python.org/downloads/

2. **Node.js 18+**
   - Check: `node --version`
   - Download: https://nodejs.org/

3. **PostgreSQL 15+**
   - macOS: `brew install postgresql@15`
   - Windows: https://www.postgresql.org/download/windows/
   - Linux: `sudo apt install postgresql postgresql-contrib`

## Complete Setup (Step-by-Step)

### Step 1: Extract Project

```bash
# Extract h2open-project folder to your preferred location
cd /path/to/h2open-project
```

### Step 2: Set Up PostgreSQL Database

```bash
# Start PostgreSQL (if not running)
# macOS:
brew services start postgresql@15

# Linux:
sudo systemctl start postgresql

# Connect to PostgreSQL
psql -d postgres

# Run these SQL commands:
CREATE DATABASE h2open_db;
CREATE USER h2open_user WITH PASSWORD 'h2open_password';
GRANT ALL PRIVILEGES ON DATABASE h2open_db TO h2open_user;
\q

# Grant schema permissions (PostgreSQL 15 requirement)
psql -d h2open_db

GRANT ALL ON SCHEMA public TO h2open_user;
GRANT USAGE ON SCHEMA public TO h2open_user;
ALTER DEFAULT PRIVILEGES IN SCHEMA public GRANT ALL ON TABLES TO h2open_user;
ALTER DEFAULT PRIVILEGES IN SCHEMA public GRANT ALL ON SEQUENCES TO h2open_user;
\q
```

### Step 3: Set Up Backend

```bash
# Navigate to backend
cd backend

# Create Python virtual environment
python3 -m venv venv

# Activate virtual environment
source venv/bin/activate  # macOS/Linux
# OR
venv\Scripts\activate  # Windows

# You should see (venv) in your prompt

# Install Python dependencies
pip install -r requirements.txt

# Configure environment variables
cp .env.example .env

# Edit .env if you changed the password
# Default values work if you followed Step 2 exactly

# Test backend
python main.py
```

You should see:
```
🚀 Starting H2Open Backend API...
✅ Database tables created
INFO:     Uvicorn running on http://0.0.0.0:8000
```

✅ **Backend is running!** Keep this terminal open.

Open http://localhost:8000/docs to see the API documentation.

### Step 4: Set Up Frontend

Open a **new terminal** (keep backend running):

```bash
# Navigate to project
cd /path/to/h2open-project

# Navigate to frontend
cd frontend

# Install Node dependencies (takes 1-2 minutes)
npm install

# Start development server
npm run dev
```

You should see:
```
VITE v5.0.8  ready in 500 ms

➜  Local:   http://localhost:5173/
```

✅ **Frontend is running!** Keep this terminal open too.

Open http://localhost:5173 to see the dashboard!

### Step 5: Add Test Data

Open a **third terminal**:

```bash
cd /path/to/h2open-project/backend
source venv/bin/activate  # or venv\Scripts\activate
python test_api.py
```

This creates sample sensor readings. Now refresh http://localhost:5173 to see the data!

## Development Workflow

### Daily Startup

You'll run these two commands in separate terminals:

**Terminal 1 - Backend:**
```bash
cd h2open-project/backend
source venv/bin/activate
python main.py
```

**Terminal 2 - Frontend:**
```bash
cd h2open-project/frontend
npm run dev
```

That's it! Both services will auto-reload when you edit code.

### Making Changes

**Backend Changes (Python):**
1. Edit files in `backend/app/`
2. Save
3. Backend auto-reloads
4. Test at http://localhost:8000/docs

**Frontend Changes (React):**
1. Edit files in `frontend/src/`
2. Save
3. Browser auto-refreshes
4. See changes at http://localhost:5173

### Stopping Services

Press `Ctrl+C` in each terminal to stop the servers.

## File Structure Reference

```
h2open-project/
│
├── backend/                    # All backend code
│   ├── app/
│   │   ├── routers/           # API endpoints
│   │   │   ├── readings.py    # Sensor data routes
│   │   │   ├── status.py      # Buoy status routes
│   │   │   └── websocket.py   # Real-time updates
│   │   ├── database.py        # DB connection
│   │   ├── models.py          # Database tables
│   │   └── schemas.py         # Data validation
│   ├── main.py                # 🚀 START BACKEND HERE
│   ├── requirements.txt       # Python packages
│   └── .env                   # Database config
│
├── frontend/                   # All frontend code
│   ├── src/
│   │   ├── components/
│   │   │   └── Layout.jsx     # Navigation bar
│   │   ├── pages/
│   │   │   ├── Readings.jsx   # Live data page
│   │   │   ├── Status.jsx     # Buoy health page
│   │   │   └── History.jsx    # Charts page
│   │   ├── services/
│   │   │   └── api.js         # Backend communication
│   │   ├── App.jsx            # React app setup
│   │   └── index.css          # Tailwind styles
│   ├── package.json           # Node packages
│   └── tailwind.config.js     # Theme colors
│
├── README.md                   # Project overview
└── .gitignore                 # Git exclusions
```

## URLs to Bookmark

- **Frontend Dashboard:** http://localhost:5173
- **Backend API Docs:** http://localhost:8000/docs
- **Backend Health:** http://localhost:8000/health
- **Database:** localhost:5432 (use psql or pgAdmin)

## Common Tasks

### View Database Contents

```bash
psql -U h2open_user -d h2open_db

# View all readings
SELECT * FROM sensor_readings ORDER BY timestamp DESC LIMIT 10;

# View buoy status
SELECT * FROM buoy_status;

# Exit
\q
```

### Create Test Reading via API

```bash
curl -X POST "http://localhost:8000/api/v1/readings" \
  -H "Content-Type: application/json" \
  -d '{
    "buoy_id": "buoy_001",
    "ecoli_cfu": 180.5,
    "temperature": 22.3
  }'
```

Or use the interactive docs at http://localhost:8000/docs

### Update Frontend Logo

1. Add your logo to `frontend/public/logo.png`
2. Edit `frontend/src/components/Layout.jsx`:
```jsx
<img src="/logo.png" alt="H2Open" className="h-10 w-10" />
```

### Change Theme Colors

Edit `frontend/tailwind.config.js`:
```js
colors: {
  primary: {
    500: '#your-color',
    600: '#your-darker-color',
  }
}
```

## Troubleshooting

### Backend Issues

**"Permission denied for schema public"**
- Run the schema permissions grants from Step 2
- Make sure you're connected to h2open_db, not postgres

**"Port 8000 already in use"**
- Check if backend is already running
- Kill process: `lsof -ti:8000 | xargs kill -9`
- Or change port in `backend/main.py`

**"Can't connect to database"**
- PostgreSQL not running: `brew services start postgresql@15`
- Wrong password in `.env` file
- Test connection: `psql -U h2open_user -d h2open_db`

### Frontend Issues

**"npm: command not found"**
- Install Node.js from https://nodejs.org
- Restart terminal after installing

**"Cannot connect to backend"**
- Backend must be running at localhost:8000
- Check http://localhost:8000/health
- Look for CORS errors in browser console (F12)

**"WebSocket not connecting"**
- Backend must be running
- Check browser console for errors
- Look for "Live" indicator in top-right (should be green)

### Database Issues

**"psql: command not found"**
- Add PostgreSQL to PATH
- macOS: `echo 'export PATH="/opt/homebrew/opt/postgresql@15/bin:$PATH"' >> ~/.zshrc`

**"Connection refused"**
- PostgreSQL not started
- macOS: `brew services list` and `brew services start postgresql@15`
- Linux: `sudo systemctl status postgresql`

## Next Steps

1. ✅ Both services running
2. ✅ Test data visible in dashboard
3. 📝 Customize frontend (logo, colors)
4. 🔌 Plan LoRa integration
5. 📊 Add more test data scenarios
6. 🚀 Prepare for deployment

## Getting Help

- **Backend errors:** Check terminal where `python main.py` is running
- **Frontend errors:** Check browser console (F12)
- **Database errors:** Check `psql` connection
- **API testing:** Use http://localhost:8000/docs

## Production Deployment (Future)

When ready to deploy:

**Backend:**
```bash
cd backend
# Use Gunicorn or Uvicorn with process manager
# Deploy to Heroku, DigitalOcean, AWS, etc.
```

**Frontend:**
```bash
cd frontend
npm run build
# Deploy dist/ folder to Netlify, Vercel, or S3
```

**Database:**
- Use managed PostgreSQL (AWS RDS, DigitalOcean, Heroku)
- Enable TimescaleDB extension

**Happy coding! 🚀**
