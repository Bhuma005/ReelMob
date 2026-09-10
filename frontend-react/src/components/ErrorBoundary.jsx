import React from 'react';
import { AlertTriangle, RotateCcw } from 'lucide-react';
import { Button } from './ui/Button';

export class ErrorBoundary extends React.Component {
  constructor(props) {
    super(props);
    this.state = { hasError: false, error: null };
  }

  static getDerivedStateFromError(error) {
    return { hasError: true, error };
  }

  componentDidCatch(error, errorInfo) {
    console.error('ErrorBoundary caught an error:', error, errorInfo);
  }
	  render() {
    if (this.state.hasError) {
      return (
        <div className="min-h-screen bg-background text-foreground flex items-center justify-center p-6">
          <div className="max-w-md w-full p-6 rounded-xl bg-surface border border-border text-center space-y-4 shadow-2xl">
            <div className="w-12 h-12 rounded-full bg-danger/10 text-danger flex items-center justify-center mx-auto">
              <AlertTriangle className="w-6 h-6" />
            </div>
            <h2 className="text-lg font-bold">Application Encountered an Error</h2>
            <p className="text-xs text-text-muted font-mono leading-relaxed bg-black/40 p-3 rounded border border-border/60 text-left overflow-auto max-h-32">
              {this.state.error.message || String(this.state.error)}
            </p>
            <div className="pt-2 flex justify-center gap-3">
              <Button 
                variant="secondary" 
                size="sm"
                className="bg-accent text-black font-semibold"
                onClick={() => {
                  this.setState({ hasError: false, error: null });
                  window.location.reload();
                }}
              >
                <RotateCcw className="w-3.5 h-3.5 mr-1.5" /> Reload ReelGrab
              </Button>
            </div>
          </div>
        </div>
      );
    }

    return this.props.children;
  }
}
