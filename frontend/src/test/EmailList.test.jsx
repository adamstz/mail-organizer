import { describe, it, expect, vi } from 'vitest';
import { render, screen, fireEvent } from '@testing-library/react';
import EmailList from '../components/EmailList';

describe('EmailList Component', () => {
  it('renders email list with correct number of items', () => {
    render(<EmailList />);
    const emailItems = screen.getAllByRole('listitem');
    expect(emailItems).toHaveLength(3); // We have 3 example emails
  });

  it('shows email details when clicked', async () => {
    render(<EmailList />);
    const firstEmail = screen.getByText('Project Update Meeting');
    fireEvent.click(firstEmail);
    
    // Check if the expanded content is visible
    expect(screen.getByText(/Dear team/)).toBeInTheDocument();
  });

  it('deletes email when delete button is clicked', () => {
    render(<EmailList />);
    const deleteButtons = screen.getAllByLabelText('delete');
    const initialEmails = screen.getAllByRole('listitem');
    
    fireEvent.click(deleteButtons[0]);
    
    const remainingEmails = screen.getAllByRole('listitem');
    expect(remainingEmails.length).toBe(initialEmails.length - 1);
  });

  it('displays priority chips with correct colors', () => {
    render(<EmailList />);
    const highPriority = screen.getByText('High');
    const mediumPriority = screen.getByText('Medium');
    const lowPriority = screen.getByText('Low');

    expect(highPriority).toHaveClass('MuiChip-colorError');
    expect(mediumPriority).toHaveClass('MuiChip-colorWarning');
    expect(lowPriority).toHaveClass('MuiChip-colorSuccess');
  });
});