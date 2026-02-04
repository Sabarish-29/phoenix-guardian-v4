import { render, screen, fireEvent } from '@testing-library/react';
import { describe, it, expect, vi } from 'vitest';
import { Provider } from 'react-redux';
import { configureStore } from '@reduxjs/toolkit';
import ThreatDetailModal from '../ThreatDetailModal';
import threatsReducer from '../../../store/slices/threatsSlice';
import type { Threat } from '../../../types/threat';

const mockThreat: Threat = {
  id: 'threat-1',
  severity: 'critical',
  title: 'Ransomware Detected',
  description: 'BlackCat ransomware variant detected',
  threatType: 'ransomware',
  status: 'active',
  confidence: 0.95,
  createdAt: '2024-01-15T10:30:00Z',
  updatedAt: '2024-01-15T10:30:00Z',
  sourceIp: '10.0.0.50',
  targetSystem: 'EHR-Primary',
  indicators: ['hash123', 'domain.bad'],
  mitreTactics: ['T1486', 'T1059'],
  acknowledged: false,
};

const createTestStore = () => configureStore({
  reducer: {
    threats: threatsReducer,
  },
});

const renderWithProvider = (ui: React.ReactElement) => {
  return render(
    <Provider store={createTestStore()}>
      {ui}
    </Provider>
  );
};

describe('ThreatDetailModal', () => {
  it('renders threat details', () => {
    renderWithProvider(<ThreatDetailModal threat={mockThreat} onClose={() => {}} />);
    
    expect(screen.getByText('Ransomware Detected')).toBeInTheDocument();
    expect(screen.getByText('BlackCat ransomware variant detected')).toBeInTheDocument();
  });

  it('displays severity badge', () => {
    renderWithProvider(<ThreatDetailModal threat={mockThreat} onClose={() => {}} />);
    expect(screen.getByText('critical')).toBeInTheDocument();
  });

  it('shows source IP and target system', () => {
    renderWithProvider(<ThreatDetailModal threat={mockThreat} onClose={() => {}} />);
    expect(screen.getByText('10.0.0.50')).toBeInTheDocument();
    expect(screen.getByText('EHR-Primary')).toBeInTheDocument();
  });

  it('displays indicators', () => {
    renderWithProvider(<ThreatDetailModal threat={mockThreat} onClose={() => {}} />);
    expect(screen.getByText('hash123')).toBeInTheDocument();
    expect(screen.getByText('domain.bad')).toBeInTheDocument();
  });

  it('displays MITRE tactics', () => {
    renderWithProvider(<ThreatDetailModal threat={mockThreat} onClose={() => {}} />);
    expect(screen.getByText('T1486')).toBeInTheDocument();
    expect(screen.getByText('T1059')).toBeInTheDocument();
  });

  it('calls onClose when close button clicked', () => {
    const onClose = vi.fn();
    renderWithProvider(<ThreatDetailModal threat={mockThreat} onClose={onClose} />);
    
    fireEvent.click(screen.getByRole('button', { name: /close/i }));
    expect(onClose).toHaveBeenCalledTimes(1);
  });

  it('has acknowledge button for unacknowledged threats', () => {
    renderWithProvider(<ThreatDetailModal threat={mockThreat} onClose={() => {}} />);
    expect(screen.getByText('Acknowledge')).toBeInTheDocument();
  });
});
