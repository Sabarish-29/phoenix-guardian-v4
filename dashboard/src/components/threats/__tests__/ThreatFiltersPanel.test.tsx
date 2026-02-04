import { render, screen, fireEvent } from '@testing-library/react';
import { describe, it, expect, vi } from 'vitest';
import ThreatFiltersPanel from '../ThreatFiltersPanel';
import type { ThreatFilters } from '../../../types/threat';

const defaultFilters: ThreatFilters = {
  severity: [],
  status: [],
  threatType: [],
  dateRange: { start: null, end: null },
  search: '',
};

describe('ThreatFiltersPanel', () => {
  it('renders all filter sections', () => {
    render(<ThreatFiltersPanel filters={defaultFilters} onFilterChange={() => {}} />);
    
    expect(screen.getByText('Filters')).toBeInTheDocument();
    expect(screen.getByText('Severity')).toBeInTheDocument();
    expect(screen.getByText('Status')).toBeInTheDocument();
    expect(screen.getByText('Type')).toBeInTheDocument();
  });

  it('renders search input', () => {
    render(<ThreatFiltersPanel filters={defaultFilters} onFilterChange={() => {}} />);
    
    expect(screen.getByPlaceholderText('Search threats...')).toBeInTheDocument();
  });

  it('calls onFilterChange when severity is selected', () => {
    const onFilterChange = vi.fn();
    render(<ThreatFiltersPanel filters={defaultFilters} onFilterChange={onFilterChange} />);
    
    fireEvent.click(screen.getByText('Critical'));
    expect(onFilterChange).toHaveBeenCalled();
  });

  it('shows selected filters as active', () => {
    const filtersWithSeverity: ThreatFilters = {
      ...defaultFilters,
      severity: ['critical'],
    };
    render(<ThreatFiltersPanel filters={filtersWithSeverity} onFilterChange={() => {}} />);
    
    const criticalButton = screen.getByText('Critical').closest('button');
    expect(criticalButton).toHaveClass('bg-red-500/30');
  });

  it('has a clear filters button', () => {
    render(<ThreatFiltersPanel filters={defaultFilters} onFilterChange={() => {}} />);
    expect(screen.getByText('Clear')).toBeInTheDocument();
  });

  it('clears all filters when clear button clicked', () => {
    const onFilterChange = vi.fn();
    const activeFilters: ThreatFilters = {
      ...defaultFilters,
      severity: ['critical', 'high'],
      status: ['active'],
    };
    render(<ThreatFiltersPanel filters={activeFilters} onFilterChange={onFilterChange} />);
    
    fireEvent.click(screen.getByText('Clear'));
    expect(onFilterChange).toHaveBeenCalledWith(defaultFilters);
  });
});
