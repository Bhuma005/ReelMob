import React from 'react';
import { describe, it, expect, vi } from 'vitest';
import { render, screen, fireEvent } from '@testing-library/react';
import { ConfirmDialog } from '../components/ui/ConfirmDialog';

describe('ConfirmDialog component', () => {
  it('does not render anything when isOpen is false', () => {
    const { container } = render(
      <ConfirmDialog
        isOpen={false}
        title="Delete video?"
        description="This cannot be undone."
        onConfirm={() => {}}
        onClose={() => {}}
      />
    );
    expect(container.firstChild).toBeNull();
  });

  it('renders title, description, and action buttons when open', () => {
    render(
      <ConfirmDialog
        isOpen={true}
        title="Delete this video?"
        description="Permanently delete from cloud storage."
        confirmText="Delete Video"
        cancelText="Keep Video"
        onConfirm={() => {}}
        onClose={() => {}}
      />
    );

    expect(screen.getByText('Delete this video?')).toBeInTheDocument();
    expect(screen.getByText('Permanently delete from cloud storage.')).toBeInTheDocument();
    expect(screen.getByRole('button', { name: 'Delete Video' })).toBeInTheDocument();
    expect(screen.getByRole('button', { name: 'Keep Video' })).toBeInTheDocument();
  });

  it('does not call onConfirm until the confirm button is explicitly clicked', () => {
    const onConfirmMock = vi.fn();
    const onCloseMock = vi.fn();

    render(
      <ConfirmDialog
        isOpen={true}
        title="Confirm action"
        description="Blocking confirmation test"
        onConfirm={onConfirmMock}
        onClose={onCloseMock}
      />
    );

    // Initial render: action is blocked
    expect(onConfirmMock).not.toHaveBeenCalled();

    // Clicking cancel does not trigger confirm
    fireEvent.click(screen.getByRole('button', { name: 'Cancel' }));
    expect(onConfirmMock).not.toHaveBeenCalled();
    expect(onCloseMock).toHaveBeenCalledTimes(1);

    // Clicking confirm invokes the confirm callback
    fireEvent.click(screen.getByRole('button', { name: 'Confirm' }));
    expect(onConfirmMock).toHaveBeenCalledTimes(1);
  });

  it('closes when Escape key is pressed', () => {
    const onCloseMock = vi.fn();

    render(
      <ConfirmDialog
        isOpen={true}
        title="Dismissible modal"
        description="Escape test"
        onConfirm={() => {}}
        onClose={onCloseMock}
      />
    );

    fireEvent.keyDown(window, { key: 'Escape' });
    expect(onCloseMock).toHaveBeenCalledTimes(1);
  });

  it('disables cancel button and shows loading state when isLoading is true', () => {
    render(
      <ConfirmDialog
        isOpen={true}
        title="Deleting..."
        description="Please wait"
        isLoading={true}
        onConfirm={() => {}}
        onClose={() => {}}
      />
    );

    const cancelButton = screen.getByRole('button', { name: 'Cancel' });
    expect(cancelButton).toBeDisabled();
  });
});
