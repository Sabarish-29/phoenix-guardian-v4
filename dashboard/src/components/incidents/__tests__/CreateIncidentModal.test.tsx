import { render, screen, fireEvent } from '@testing-library/react';
import { describe, it, expect, vi } from 'vitest';
import { Provider } from 'react-redux';
import { configureStore } from '@reduxjs/toolkit';
import CreateIncidentModal from '../CreateIncidentModal';
import incidentsReducer from '../../../store/slices/incidentsSlice';

const createTestStore = () => configureStore({
  reducer: {
    incidents: incidentsReducer,
  },
});

const renderWithProvider = (ui: React.ReactElement) => {
  return render(
    <Provider store={createTestStore()}>
      {ui}
    </Provider>
  );
};

describe('CreateIncidentModal', () => {
  it('renders create form', () => {
    renderWithProvider(<CreateIncidentModal onClose={() => {}} />);
    expect(screen.getByText('Create Incident')).toBeInTheDocument();
  });

  it('has title input field', () => {
    renderWithProvider(<CreateIncidentModal onClose={() => {}} />);
    expect(screen.getByPlaceholderText('Brief incident title')).toBeInTheDocument();
  });

  it('has priority select with options', () => {
    renderWithProvider(<CreateIncidentModal onClose={() => {}} />);
    expect(screen.getByText('P1 - Critical')).toBeInTheDocument();
  });

  it('has category select with options', () => {
    renderWithProvider(<CreateIncidentModal onClose={() => {}} />);
    expect(screen.getByRole('combobox', { name: /category/i }) || screen.getByText('Malware')).toBeInTheDocument();
  });

  it('has description textarea', () => {
    renderWithProvider(<CreateIncidentModal onClose={() => {}} />);
    expect(screen.getByPlaceholderText('Describe the incident...')).toBeInTheDocument();
  });

  it('calls onClose when cancel clicked', () => {
    const onClose = vi.fn();
    renderWithProvider(<CreateIncidentModal onClose={onClose} />);
    
    fireEvent.click(screen.getByText('Cancel'));
    expect(onClose).toHaveBeenCalledTimes(1);
  });

  it('disables submit when title is empty', () => {
    renderWithProvider(<CreateIncidentModal onClose={() => {}} />);
    
    const submitButton = screen.getByText('Create Incident');
    expect(submitButton).toBeDisabled();
  });

  it('enables submit when title is provided', () => {
    renderWithProvider(<CreateIncidentModal onClose={() => {}} />);
    
    fireEvent.change(screen.getByPlaceholderText('Brief incident title'), {
      target: { value: 'Test Incident' },
    });
    
    const submitButton = screen.getByText('Create Incident');
    expect(submitButton).not.toBeDisabled();
  });

  it('allows changing priority', () => {
    renderWithProvider(<CreateIncidentModal onClose={() => {}} />);
    
    const prioritySelect = screen.getByDisplayValue('P2 - High');
    fireEvent.change(prioritySelect, { target: { value: 'P1' } });
    expect(prioritySelect).toHaveValue('P1');
  });
});
