import { useEffect, useState, useRef } from 'react';
import { MapContainer, TileLayer, CircleMarker, Popup, useMap } from 'react-leaflet';
import { useAppDispatch, useAppSelector } from '../hooks/useStore';
import { fetchThreats, selectAllThreats } from '../store/slices/threatsSlice';
import type { Threat, ThreatSeverity } from '../types/threat';
import { format } from 'date-fns';
import clsx from 'clsx';
import 'leaflet/dist/leaflet.css';

// Severity colors for map markers
const severityColors: Record<ThreatSeverity, string> = {
  critical: '#dc2626',
  high: '#ea580c',
  medium: '#ca8a04',
  low: '#16a34a',
  info: '#2563eb',
};

interface ThreatMarker {
  id: string;
  position: [number, number];
  severity: ThreatSeverity;
  count: number;
  threats: Threat[];
}

// Component to handle map updates
function MapController({ center }: { center: [number, number] }) {
  const map = useMap();
  
  useEffect(() => {
    map.setView(center, map.getZoom());
  }, [center, map]);
  
  return null;
}

/**
 * ThreatMap - Geographic visualization of threats
 */
export default function ThreatMap() {
  const dispatch = useAppDispatch();
  const threats = useAppSelector(selectAllThreats);
  const [markers, setMarkers] = useState<ThreatMarker[]>([]);
  const [selectedSeverities, setSelectedSeverities] = useState<ThreatSeverity[]>([
    'critical', 'high', 'medium', 'low'
  ]);
  const [mapCenter, setMapCenter] = useState<[number, number]>([39.8283, -98.5795]); // US center

  useEffect(() => {
    dispatch(fetchThreats(undefined));
  }, [dispatch]);

  // Aggregate threats by location
  useEffect(() => {
    const locationMap = new Map<string, ThreatMarker>();
    
    threats.forEach((threat) => {
      if (!threat.sourceLocation) return;
      if (!selectedSeverities.includes(threat.severity)) return;
      
      const { latitude, longitude } = threat.sourceLocation;
      const key = `${latitude.toFixed(2)},${longitude.toFixed(2)}`;
      
      if (locationMap.has(key)) {
        const existing = locationMap.get(key)!;
        existing.count += 1;
        existing.threats.push(threat);
        // Keep the highest severity
        const severityOrder: ThreatSeverity[] = ['critical', 'high', 'medium', 'low', 'info'];
        if (severityOrder.indexOf(threat.severity) < severityOrder.indexOf(existing.severity)) {
          existing.severity = threat.severity;
        }
      } else {
        locationMap.set(key, {
          id: key,
          position: [latitude, longitude],
          severity: threat.severity,
          count: 1,
          threats: [threat],
        });
      }
    });
    
    setMarkers(Array.from(locationMap.values()));
  }, [threats, selectedSeverities]);

  const toggleSeverity = (severity: ThreatSeverity) => {
    setSelectedSeverities(prev => 
      prev.includes(severity)
        ? prev.filter(s => s !== severity)
        : [...prev, severity]
    );
  };

  return (
    <div className="space-y-4">
      {/* Filter Controls */}
      <div className="flex flex-wrap items-center gap-4 bg-dashboard-card rounded-xl border border-dashboard-border p-4">
        <span className="text-dashboard-muted">Show:</span>
        {(['critical', 'high', 'medium', 'low'] as ThreatSeverity[]).map((severity) => (
          <button
            key={severity}
            onClick={() => toggleSeverity(severity)}
            className={clsx(
              'flex items-center gap-2 px-3 py-1 rounded-full text-sm font-medium transition-colors capitalize',
              selectedSeverities.includes(severity)
                ? 'bg-dashboard-border text-white'
                : 'text-dashboard-muted hover:text-white'
            )}
          >
            <span 
              className="w-3 h-3 rounded-full"
              style={{ backgroundColor: severityColors[severity] }}
            />
            {severity}
          </button>
        ))}
        <span className="ml-auto text-sm text-dashboard-muted">
          {markers.reduce((sum, m) => sum + m.count, 0)} threats from {markers.length} locations
        </span>
      </div>

      {/* Map Container */}
      <div className="h-[600px] rounded-xl overflow-hidden border border-dashboard-border">
        <MapContainer
          center={mapCenter}
          zoom={4}
          className="h-full w-full"
          style={{ background: '#1e293b' }}
        >
          <MapController center={mapCenter} />
          <TileLayer
            attribution='&copy; <a href="https://carto.com/">CARTO</a>'
            url="https://{s}.basemaps.cartocdn.com/dark_all/{z}/{x}/{y}{r}.png"
          />
          {markers.map((marker) => (
            <CircleMarker
              key={marker.id}
              center={marker.position}
              radius={Math.min(8 + marker.count * 2, 25)}
              pathOptions={{
                color: severityColors[marker.severity],
                fillColor: severityColors[marker.severity],
                fillOpacity: 0.6,
                weight: 2,
              }}
            >
              <Popup className="threat-popup">
                <div className="p-2 min-w-[200px]">
                  <div className="flex items-center justify-between mb-2">
                    <span className="font-semibold text-gray-900">
                      {marker.count} Threat{marker.count !== 1 ? 's' : ''}
                    </span>
                    <span 
                      className="px-2 py-0.5 rounded-full text-xs text-white capitalize"
                      style={{ backgroundColor: severityColors[marker.severity] }}
                    >
                      {marker.severity}
                    </span>
                  </div>
                  <div className="space-y-1 max-h-[150px] overflow-y-auto">
                    {marker.threats.slice(0, 5).map((threat) => (
                      <div key={threat.id} className="text-sm">
                        <p className="font-medium text-gray-800 truncate">{threat.title}</p>
                        <p className="text-gray-500 text-xs">
                          {format(new Date(threat.timestamp), 'MMM d, HH:mm')}
                        </p>
                      </div>
                    ))}
                    {marker.threats.length > 5 && (
                      <p className="text-xs text-gray-500">
                        +{marker.threats.length - 5} more
                      </p>
                    )}
                  </div>
                </div>
              </Popup>
            </CircleMarker>
          ))}
        </MapContainer>
      </div>

      {/* Legend */}
      <div className="flex items-center justify-center gap-6 text-sm text-dashboard-muted">
        <span>Marker size indicates threat count</span>
        <span>•</span>
        <span>Click markers for details</span>
      </div>
    </div>
  );
}
