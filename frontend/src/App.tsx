import React from 'react';
import { BrowserRouter, Routes, Route } from 'react-router-dom';
import { SecurityDashboard } from './pages/SecurityDashboard';
import { AgentView } from './pages/AgentView';

function App() {
  return (
    <BrowserRouter>
      <Routes>
        <Route path="/" element={<SecurityDashboard />} />
        <Route path="/agent" element={<AgentView />} />
      </Routes>
    </BrowserRouter>
  );
}

export default App;