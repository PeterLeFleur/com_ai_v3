markdown# COM-AI v3 Frontend

This React application provides the user interface for COM-AI v3.

## Important Notes

- **Separate Build System**: This frontend is independent of the Python backend
- **Not Registry Tracked**: Frontend files are NOT tracked in `FILE_REGISTRY.csv`
- **Optional Component**: The backend API works standalone without the frontend

## Development
```bash
# Install dependencies
npm install

# Start development server
npm start

# Build for production
npm run build
Backend Integration
The frontend connects to the FastAPI backend at:

Development: http://localhost:8000
API Documentation: http://localhost:8000/docs
WebSocket: ws://localhost:8000/ws

File Structure
src/
├── components/     # React components
├── services/       # API integration
├── hooks/         # Custom React hooks
├── utils/         # Frontend utilities
└── App.js         # Main application

### `frontend/src/App.js`
```javascript
import React from 'react';

function App() {
  return (
    <div className="App">
      <header className="App-header">
        <h1>COM-AI v3 - Brain Interface</h1>
        <p>Multi-Provider AI Brain System</p>
      </header>
    </div>
  );
}

export default App;