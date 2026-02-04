import { Routes, Route, Navigate } from 'react-router-dom';
import { useEffect } from 'react';
import Layout from './components/Layout';
import DashboardHome from './pages/DashboardHome';
import ThreatFeed from './pages/ThreatFeed';
import ThreatMap from './pages/ThreatMap';
import Honeytokens from './pages/Honeytokens';
import Evidence from './pages/Evidence';
import Incidents from './pages/Incidents';
import Settings from './pages/Settings';
import FederatedView from './pages/FederatedView';
import { useAppDispatch } from './hooks/useStore';
import { initializeWebSocket } from './store/slices/websocketSlice';

/**
 * Phoenix Guardian Security Dashboard
 * 
 * Real-time security command center for hospital security teams.
 * Provides threat visualization, incident management, and evidence handling.
 */
function App() {
  const dispatch = useAppDispatch();

  useEffect(() => {
    // Initialize WebSocket connection on app mount
    dispatch(initializeWebSocket());
  }, [dispatch]);

  return (
    <Routes>
      <Route path="/" element={<Layout />}>
        <Route index element={<DashboardHome />} />
        <Route path="threats" element={<ThreatFeed />} />
        <Route path="map" element={<ThreatMap />} />
        <Route path="honeytokens" element={<Honeytokens />} />
        <Route path="evidence" element={<Evidence />} />
        <Route path="incidents" element={<Incidents />} />
        <Route path="federated" element={<FederatedView />} />
        <Route path="settings" element={<Settings />} />
        <Route path="*" element={<Navigate to="/" replace />} />
      </Route>
    </Routes>
  );
}

export default App;
