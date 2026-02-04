import { render, screen, fireEvent } from '@testing-library/react';
import { describe, it, expect, vi } from 'vitest';
import IncidentDetailModal from '../IncidentDetailModal';
import type { Incident } from '../../../types/incident';

const mockIncident: Incident = {
  id: 'inc-1',
  title: 'Ransomware Attack on EHR System',
  description: 'BlackCat ransomware detected attempting to encrypt patient records. Initial vector appears to be phishing email.',
  priority: 'P1',
  severity: 'critical',
  status: 'investigating',
  category: 'ransomware',
  affectedAssets: ['EHR-Primary', 'EHR-Backup', 'Lab-System'],
  affectedDepartments: ['Radiology', 'Emergency'],
  threatIds: ['threat-1', 'threat-2'],
  assignee: { id: 'user-1', name: 'John Analyst', email: 'john@hospital.org' },
  createdAt: '2024-01-15T10:00:00Z',
  updatedAt: '2024-01-15T12:00:00Z',
  slaBreach: false,
  containmentActions: ['Network isolation', 'User account disabled'],
  remediationActions: [],
};

describe('IncidentDetailModal', () => {
  it('renders incident title', () => {
    render(<IncidentDetailModal incident={mockIncident} onClose={() => {}} />);
    expect(screen.getByText('Ransomware Attack on EHR System')).toBeInTheDocument();
  });

  it('displays full description', () => {
    render(<IncidentDetailModal incident={mockIncident} onClose={() => {}} />);
    expect(screen.getByText(/BlackCat ransomware detected/)).toBeInTheDocument();
  });

  it('shows priority badge', () => {
    render(<IncidentDetailModal incident={mockIncident} onClose={() => {}} />);
    expect(screen.getByText('P1')).toBeInTheDocument();
  });

  it('displays status', () => {
    render(<IncidentDetailModal incident={mockIncident} onClose={() => {}} />);
    expect(screen.getByText('investigating')).toBeInTheDocument();
  });

  it('shows category', () => {
    render(<IncidentDetailModal incident={mockIncident} onClose={() => {}} />);
    expect(screen.getByText('ransomware')).toBeInTheDocument();
  });

  it('displays affected assets', () => {
    render(<IncidentDetailModal incident={mockIncident} onClose={() => {}} />);
    expect(screen.getByText('EHR-Primary')).toBeInTheDocument();
    expect(screen.getByText('EHR-Backup')).toBeInTheDocument();
    expect(screen.getByText('Lab-System')).toBeInTheDocument();
  });

  it('shows containment actions', () => {
    render(<IncidentDetailModal incident={mockIncident} onClose={() => {}} />);
    expect(screen.getByText('Network isolation')).toBeInTheDocument();
    expect(screen.getByText('User account disabled')).toBeInTheDocument();
  });

  it('displays assignee name', () => {
    render(<IncidentDetailModal incident={mockIncident} onClose={() => {}} />);
    expect(screen.getByText('John Analyst')).toBeInTheDocument();
  });

  it('calls onClose when close button clicked', () => {
    const onClose = vi.fn();
    render(<IncidentDetailModal incident={mockIncident} onClose={onClose} />);
    
    fireEvent.click(screen.getByText('Close'));
    expect(onClose).toHaveBeenCalledTimes(1);
  });

  it('has update status button', () => {
    render(<IncidentDetailModal incident={mockIncident} onClose={() => {}} />);
    expect(screen.getByText('Update Status')).toBeInTheDocument();
  });
});
