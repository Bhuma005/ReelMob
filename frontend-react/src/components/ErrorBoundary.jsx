import React from 'react';
import { AlertTriangle, RotateCcw, RefreshCw } from 'lucide-react';
import { Button } from './ui/Button';
import { 
  isStaleChunkError, 
  handleStaleChunkReload, 
  clearStaleChunkReloadMarker 
} from '../utils/chunkReload';

export class ErrorBoundary extends React.Component {
  constructor(props) {
    super(props);
    this.state = { hasError: false, error: null, reloading: false };
  }

  static getDerivedStateFromError(error) {
    return { hasError: true, error };
  }

  componentDidCatch(error, errorInfo) {
    console.error('ErrorBoundary caught an error:', error, errorInfo);

    // Attempt automatic guarded one-time reload for stale chunk / dynamic import errors
    if (isStaleChunkError(error)) {
      const reloaded = handleStaleChunkReload(error);
      if (reloaded) {
        this.setState({ reloading: true });
      }
    }
  }

  handleManualReload = () => {
    clearStaleChunkReloadMarker();
    this.setState({ hasError: false, error: null, reloading: false });
    window.location.reload();
  };

  render() {
    if (this.state.reloading) {
      return (
        <div className="min-h-screen bg-background text-foreground flex items-center justify-center p-6">
          <div className="max-w-md w-full p-6 rounded-xl bg-surface border border-border text-center space-y-3 shadow-2xl">
            <div className="w-10 h-10 rounded-full bg-accent/15 text-accent flex items-center justify-center mx-auto">
              <RefreshCw className="w-5 h-5 animate-spin" />
            </div>
            <h2 className="text-base font-bold">Updating ReelsMob...</h2>
            <p className="text-xs text-text-muted leading-relaxed">
              A newer version of the application was deployed. Refreshing assets now...
            </p>
          </div>
        </div>
      );
    }

    if (this.state.hasError) {
      const isChunk = isStaleChunkError(this.state.error);

      return (
        <div className="min-h-screen bg-background text-foreground flex items-center justify-center p-6">
          <div className="max-w-md w-full p-6 rounded-xl bg-surface border border-border text-center space-y-4 shadow-2xl">
            <div className={`w-12 h-12 rounded-full flex items-center justify-center mx-auto ${
              isChunk ? 'bg-accent/15 text-accent' : 'bg-danger/10 text-danger'
            }`}>
              <AlertTriangle className="w-6 h-6" />
            </div>
            <h2 className="text-lg font-bold">
              {isChunk ? 'New Version Available' : 'Application Encountered an Error'}
            </h2>
            <p className="text-xs text-text-muted font-mono leading-relaxed bg-black/40 p-3 rounded border border-border/60 text-left overflow-auto max-h-32">
              {this.state.error?.message || String(this.state.error)}
            </p>
            {isChunk && (
              <p className="text-xs text-text-muted">
                Your browser had an older cached session from before the latest deployment. Click below to reload the newest version.
              </p>
            )}
            <div className="pt-2 flex justify-center gap-3">
              <Button 
                variant="secondary" 
                size="sm"
                className="bg-accent text-black font-semibold"
                onClick={this.handleManualReload}
              >
                <RotateCcw className="w-3.5 h-3.5 mr-1.5" /> 
                {isChunk ? 'Reload Latest Version' : 'Reload ReelGrab'}
              </Button>
            </div>
          </div>
        </div>
      );
    }

    return this.props.children;
  }
}
