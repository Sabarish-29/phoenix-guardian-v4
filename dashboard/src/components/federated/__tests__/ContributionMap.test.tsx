import { render, screen } from '@testing-library/react';
import { describe, it, expect } from 'vitest';
import ContributionMap from '../ContributionMap';
import type { HospitalContribution } from '../../../types/federated';

const mockContributions: HospitalContribution[] = [
  {
    hospitalId: 'hosp-1',
    hospitalName: 'Metro General Hospital',
    region: 'Northeast',
    contributionCount: 150,
    lastContribution: '2024-01-15T12:00:00Z',
    qualityScore: 0.92,
    privacyCompliant: true,
  },
  {
    hospitalId: 'hosp-2',
    hospitalName: 'Central Medical Center',
    region: 'Northeast',
    contributionCount: 120,
    lastContribution: '2024-01-14T18:00:00Z',
    qualityScore: 0.88,
    privacyCompliant: true,
  },
  {
    hospitalId: 'hosp-3',
    hospitalName: 'Pacific Health System',
    region: 'West',
    contributionCount: 200,
    lastContribution: '2024-01-15T10:00:00Z',
    qualityScore: 0.95,
    privacyCompliant: true,
  },
  {
    hospitalId: 'hosp-4',
    hospitalName: 'Southern Regional',
    region: 'Southeast',
    contributionCount: 80,
    lastContribution: '2024-01-13T14:00:00Z',
    qualityScore: 0.75,
    privacyCompliant: false,
  },
];

describe('ContributionMap', () => {
  it('renders contribution summary', () => {
    render(<ContributionMap contributions={mockContributions} />);
    expect(screen.getByText('4')).toBeInTheDocument(); // Hospital count
    expect(screen.getByText('Hospitals')).toBeInTheDocument();
  });

  it('displays empty state when no contributions', () => {
    render(<ContributionMap contributions={[]} />);
    expect(screen.getByText('No contributions data available')).toBeInTheDocument();
  });

  it('shows total contributions', () => {
    render(<ContributionMap contributions={mockContributions} />);
    expect(screen.getByText('550')).toBeInTheDocument(); // Total contributions
    expect(screen.getByText('Total Contributions')).toBeInTheDocument();
  });

  it('displays average quality score', () => {
    render(<ContributionMap contributions={mockContributions} />);
    expect(screen.getByText('Avg Quality')).toBeInTheDocument();
  });

  it('groups hospitals by region', () => {
    render(<ContributionMap contributions={mockContributions} />);
    expect(screen.getByText('Northeast')).toBeInTheDocument();
    expect(screen.getByText('West')).toBeInTheDocument();
    expect(screen.getByText('Southeast')).toBeInTheDocument();
  });

  it('shows hospital names', () => {
    render(<ContributionMap contributions={mockContributions} />);
    expect(screen.getByText('Metro General Hospital')).toBeInTheDocument();
    expect(screen.getByText('Pacific Health System')).toBeInTheDocument();
  });

  it('displays privacy compliance status', () => {
    render(<ContributionMap contributions={mockContributions} />);
    // Should show checkmarks for compliant and X for non-compliant
    expect(screen.getAllByText('✓')).toHaveLength(3);
    expect(screen.getByText('✗')).toBeInTheDocument();
  });

  it('shows region hospital count', () => {
    render(<ContributionMap contributions={mockContributions} />);
    expect(screen.getByText('2 hospitals')).toBeInTheDocument(); // Northeast
    expect(screen.getByText('1 hospitals')).toBeInTheDocument(); // West and Southeast
  });
});
