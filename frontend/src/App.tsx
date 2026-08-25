import React from 'react';
import { BrowserRouter, Routes, Route, Navigate } from 'react-router-dom';
import { DemoDashboard } from './pages/DemoDashboard/DemoDashboard';
import { Dashboard } from './pages/Dashboard/Dashboard';
import { LiveCall } from './pages/LiveCall/LiveCall';
import { MediaLogs } from './pages/MediaLogs';

function App() {
  return (
    <BrowserRouter>
      <Routes>
        <Route path="/" element={<DemoDashboard />} />
        <Route path="/old-dashboard" element={<Dashboard />} />
        <Route path="/live/:id" element={<LiveCall />} />
        <Route path="/media-logs" element={<MediaLogs />} />
        {/* Redirect old routes */}
        <Route path="/agent" element={<Navigate to="/live/demo" replace />} />
      </Routes>
    </BrowserRouter>
  );
}

export default App;