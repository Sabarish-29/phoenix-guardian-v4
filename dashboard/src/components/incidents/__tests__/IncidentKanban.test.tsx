import { render, screen, fireEvent } from '@testing-library/react';
import { describe, it, expect, vi } from 'vitest';
import IncidentKanban from '../IncidentKanban';
import type { Incident } from '../../../types/incident';

const createIncident = (id: string, status: string, priority: string): Incident => ({
  id,
  title: `Incident ${id}`,
  description: 'Test incident',
  priority: priority as any,
  severity: 'high',
  status: status as any,
  category: 'malware',
  affectedAssets: [],
  affectedDepartments: [],
  threatIds: [],
  createdAt: '2024-01-15T10:00:00Z',
  updatedAt: '2024-01-15T12:00:00Z',
  slaBreach: false,
  containmentActions: [],
  remediationActions: [],
});

const mockIncidents: Incident[] = [
  createIncident('1', 'open', 'P1'),
  createIncident('2', 'open', 'P2'),
  createIncident('3', 'investigating', 'P1'),
  createIncident('4', 'contained', 'P3'),
  createIncident('5', 'resolved', 'P2'),
];

describe('IncidentKanban', () => {
  it('renders all kanban columns', () => {
    render(<IncidentKanban incidents={mockIncidents} onSelectIncident={() => {}} />);
    
    expect(screen.getByText('Open')).toBeInTheDocument();
    expect(screen.getByText('Investigating')).toBeInTheDocument();
    expect(screen.getByText('Contained')).toBeInTheDocument();
    expect(screen.getByText('Resolved')).toBeInTheDocument();
  });

  it('displays correct count per column', () => {
    render(<IncidentKanban incidents={mockIncidents} onSelectIncident={() => {}} />);
    
    // Open column should have 2
    const openColumn = screen.getByText('Open').closest('div');
    expect(openColumn).toHaveTextContent('2');
  });

  it('shows incidents in correct columns', () => {
    render(<IncidentKanban incidents={mockIncidents} onSelectIncident={() => {}} />);
    
    expect(screen.getByText('Incident 1')).toBeInTheDocument();
    expect(screen.getByText('Incident 2')).toBeInTheDocument();
    expect(screen.getByText('Incident 3')).toBeInTheDocument();
    expect(screen.getByText('Incident 4')).toBeInTheDocument();
    expect(screen.getByText('Incident 5')).toBeInTheDocument();
  });

  it('calls onSelectIncident when incident clicked', () => {
    const onSelectIncident = vi.fn();
    render(<IncidentKanban incidents={mockIncidents} onSelectIncident={onSelectIncident} />);
    
    fireEvent.click(screen.getByText('Incident 1'));
    expect(onSelectIncident).toHaveBeenCalledWith(mockIncidents[0]);
  });

  it('shows empty message for columns with no incidents', () => {
    const limitedIncidents = [createIncident('1', 'open', 'P1')];
    render(<IncidentKanban incidents={limitedIncidents} onSelectIncident={() => {}} />);
    
    expect(screen.getAllByText('No incidents')).toHaveLength(3);
  });

  it('displays priority badges', () => {
    render(<IncidentKanban incidents={mockIncidents} onSelectIncident={() => {}} />);
    
    expect(screen.getAllByText('P1')).toHaveLength(2);
    expect(screen.getAllByText('P2')).toHaveLength(2);
    expect(screen.getAllByText('P3')).toHaveLength(1);
  });
});
