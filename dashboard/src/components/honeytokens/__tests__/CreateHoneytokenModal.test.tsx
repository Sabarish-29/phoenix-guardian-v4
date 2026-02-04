import { render, screen, fireEvent } from '@testing-library/react';
import { describe, it, expect, vi } from 'vitest';
import { Provider } from 'react-redux';
import { configureStore } from '@reduxjs/toolkit';
import CreateHoneytokenModal from '../CreateHoneytokenModal';
import honeytokensReducer from '../../../store/slices/honeytokensSlice';

const createTestStore = () => configureStore({
  reducer: {
    honeytokens: honeytokensReducer,
  },
});

const renderWithProvider = (ui: React.ReactElement) => {
  return render(
    <Provider store={createTestStore()}>
      {ui}
    </Provider>
  );
};

describe('CreateHoneytokenModal', () => {
  it('renders create form', () => {
    renderWithProvider(<CreateHoneytokenModal onClose={() => {}} />);
    expect(screen.getByText('Create Honeytoken')).toBeInTheDocument();
  });

  it('has name input field', () => {
    renderWithProvider(<CreateHoneytokenModal onClose={() => {}} />);
    expect(screen.getByPlaceholderText('e.g., VIP Patient Record')).toBeInTheDocument();
  });

  it('has type select with options', () => {
    renderWithProvider(<CreateHoneytokenModal onClose={() => {}} />);
    expect(screen.getByText(/Patient Record/)).toBeInTheDocument();
  });

  it('has description textarea', () => {
    renderWithProvider(<CreateHoneytokenModal onClose={() => {}} />);
    expect(screen.getByPlaceholderText('Describe this honeytoken...')).toBeInTheDocument();
  });

  it('has location input', () => {
    renderWithProvider(<CreateHoneytokenModal onClose={() => {}} />);
    expect(screen.getByPlaceholderText('e.g., /data/patients/vip')).toBeInTheDocument();
  });

  it('calls onClose when cancel clicked', () => {
    const onClose = vi.fn();
    renderWithProvider(<CreateHoneytokenModal onClose={onClose} />);
    
    fireEvent.click(screen.getByText('Cancel'));
    expect(onClose).toHaveBeenCalledTimes(1);
  });

  it('calls onClose when X button clicked', () => {
    const onClose = vi.fn();
    renderWithProvider(<CreateHoneytokenModal onClose={onClose} />);
    
    const closeButton = document.querySelector('button svg[class*="h-6"]')?.parentElement;
    if (closeButton) fireEvent.click(closeButton);
    expect(onClose).toHaveBeenCalled();
  });

  it('disables submit when name is empty', () => {
    renderWithProvider(<CreateHoneytokenModal onClose={() => {}} />);
    
    const submitButton = screen.getByText('Create Honeytoken');
    expect(submitButton).toBeDisabled();
  });

  it('enables submit when name is provided', () => {
    renderWithProvider(<CreateHoneytokenModal onClose={() => {}} />);
    
    fireEvent.change(screen.getByPlaceholderText('e.g., VIP Patient Record'), {
      target: { value: 'Test Honeytoken' },
    });
    
    const submitButton = screen.getByText('Create Honeytoken');
    expect(submitButton).not.toBeDisabled();
  });
});
