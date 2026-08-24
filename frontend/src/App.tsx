import React from 'react';
import { BrowserRouter, Routes, Route } from 'react-router-dom';
import { SecurityDashboard } from './pages/SecurityDashboard';
import { AgentView } from './pages/AgentView';
import { MediaLogs } from './pages/MediaLogs';

function App() {
  return (
    <BrowserRouter>
      <Routes>
        <Route path="/" element={<SecurityDashboard />} />
        <Route path="/agent" element={<AgentView />} />
        <Route path="/media-logs" element={<MediaLogs />} />
      </Routes>
    </BrowserRouter>
  );
}

export default App;