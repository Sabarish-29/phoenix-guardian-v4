import { render, screen } from '@testing-library/react';
import { describe, it, expect } from 'vitest';
import PrivacyBudgetGauge from '../PrivacyBudgetGauge';
import type { PrivacyMetrics } from '../../../types/federated';

const mockMetrics: PrivacyMetrics = {
  epsilon: 1.0,
  delta: 1e-5,
  budgetUsed: 0.6,
  budgetTotal: 1.0,
  queriesThisPeriod: 150,
  noiseMultiplier: 1.1,
  nextReset: '2024-02-01T00:00:00Z',
};

describe('PrivacyBudgetGauge', () => {
  it('renders the gauge', () => {
    render(<PrivacyBudgetGauge metrics={mockMetrics} />);
    expect(screen.getByText('60.0%')).toBeInTheDocument();
    expect(screen.getByText('Used')).toBeInTheDocument();
  });

  it('displays epsilon value', () => {
    render(<PrivacyBudgetGauge metrics={mockMetrics} />);
    expect(screen.getByText('Epsilon (ε)')).toBeInTheDocument();
    expect(screen.getByText('1')).toBeInTheDocument();
  });

  it('displays delta value', () => {
    render(<PrivacyBudgetGauge metrics={mockMetrics} />);
    expect(screen.getByText('Delta (δ)')).toBeInTheDocument();
  });

  it('shows queries this period', () => {
    render(<PrivacyBudgetGauge metrics={mockMetrics} />);
    expect(screen.getByText('Queries This Period')).toBeInTheDocument();
    expect(screen.getByText('150')).toBeInTheDocument();
  });

  it('displays noise multiplier', () => {
    render(<PrivacyBudgetGauge metrics={mockMetrics} />);
    expect(screen.getByText('Noise Multiplier')).toBeInTheDocument();
    expect(screen.getByText('1.1')).toBeInTheDocument();
  });

  it('shows next reset date', () => {
    render(<PrivacyBudgetGauge metrics={mockMetrics} />);
    expect(screen.getByText('Next Reset')).toBeInTheDocument();
    expect(screen.getByText(/Feb 1/)).toBeInTheDocument();
  });

  it('shows warning when budget is low', () => {
    const lowBudgetMetrics = { ...mockMetrics, budgetUsed: 0.85 };
    render(<PrivacyBudgetGauge metrics={lowBudgetMetrics} />);
    expect(screen.getByText(/Privacy budget running low/)).toBeInTheDocument();
  });

  it('does not show warning when budget is sufficient', () => {
    render(<PrivacyBudgetGauge metrics={mockMetrics} />);
    expect(screen.queryByText(/Privacy budget running low/)).not.toBeInTheDocument();
  });
});
