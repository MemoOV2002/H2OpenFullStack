# H2Open Frontend

React dashboard for H2Open water quality monitoring system with Tailwind CSS.

## Features

✅ Real-time sensor readings with WebSocket connection
✅ Buoy status monitoring (online/offline, battery, location)
✅ Historical data visualization with interactive charts
✅ Responsive design (mobile and desktop)
✅ Clean, modern UI with Tailwind CSS

## Prerequisites

- Node.js 18+ installed
- Backend API running at http://localhost:8000

## Quick Start

```bash
# Install dependencies
npm install

# Start development server
npm run dev
```

The app will open at **http://localhost:5173**

## Project Structure

```
h2open-frontend/
├── src/
│   ├── components/
│   │   └── Layout.jsx          # Main layout with navigation
│   ├── pages/
│   │   ├── Readings.jsx        # Live sensor readings
│   │   ├── Status.jsx          # Buoy status dashboard
│   │   └── History.jsx         # Historical data & charts
│   ├── services/
│   │   └── api.js              # API client & WebSocket
│   ├── App.jsx                 # Main app component
│   ├── main.jsx                # Entry point
│   └── index.css               # Tailwind CSS
├── package.json
└── tailwind.config.js
```

## Pages

### Readings
- Live sensor data with real-time WebSocket updates
- Filter by buoy
- Safety status (Safe/Unsafe based on EPA threshold)
- E. coli levels, temperature, pH

### Status
- All buoy health monitoring
- Online/offline status
- Battery levels with visual indicators
- Last contact time
- Location information

### History
- Historical data charts (1 hour to 30 days)
- E. coli trends over time
- Temperature trends (if available)
- Statistics: average, min, max, safe/unsafe counts

## Customization

### Adding Your Project Logo

Replace the `Droplets` icon in `src/components/Layout.jsx`:

```jsx
// Option 1: Use an image
<img src="/path/to/logo.png" alt="H2Open" className="h-8 w-8" />

// Option 2: Use a different Lucide icon
import { Waves } from 'lucide-react';
<Waves className="h-6 w-6 text-white" />
```

### Changing Colors

Edit `tailwind.config.js`:

```js
theme: {
  extend: {
    colors: {
      primary: {
        // Your custom blue shades
        500: '#your-color',
        600: '#your-color',
      },
      water: {
        safe: '#your-green',
        unsafe: '#your-red',
      }
    },
  },
}
```

### Adding More Pages

1. Create new page component in `src/pages/`
2. Add route in `src/App.jsx`
3. Add navigation link in `src/components/Layout.jsx`

## API Integration

The frontend connects to your FastAPI backend:

- REST API: `http://localhost:8000/api/v1/*`
- WebSocket: `ws://localhost:8000/ws/live-data`

All API calls are in `src/services/api.js`

## Build for Production

```bash
npm run build
```

Output will be in `dist/` folder. Deploy to:
- Netlify
- Vercel
- GitHub Pages
- Your own server with NGINX

## Troubleshooting

**"Cannot connect to backend"**
- Make sure FastAPI backend is running: `cd ../h2open-backend && python main.py`
- Check API URL in `src/services/api.js`

**"WebSocket not connecting"**
- Verify WebSocket URL in `src/services/api.js`
- Check browser console for errors

**Styling not working**
- Run `npm install` to install Tailwind CSS
- Check `tailwind.config.js` and `postcss.config.js` exist

## Development Tips

- Hot reload enabled - changes appear instantly
- Check browser console for errors
- Use React DevTools for debugging
- Backend API docs: http://localhost:8000/docs

## Team

H2Open - Team 08
Lead Engineer: Guillermo Ortega
Backend Developer: Memo Ortega
