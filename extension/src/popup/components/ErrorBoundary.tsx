import React, { Component, ErrorInfo, ReactNode } from 'react';

interface ErrorBoundaryProps {
  children: ReactNode;
  fallback?: ReactNode;
  onError?: (error: Error, errorInfo: ErrorInfo) => void;
}

interface ErrorBoundaryState {
  hasError: boolean;
  error: Error | null;
}

export class ErrorBoundary extends Component<ErrorBoundaryProps, ErrorBoundaryState> {
  constructor(props: ErrorBoundaryProps) {
    super(props);
    this.state = { hasError: false, error: null };
  }

  static getDerivedStateFromError(error: Error): ErrorBoundaryState {
    return { hasError: true, error };
  }

  componentDidCatch(error: Error, errorInfo: ErrorInfo): void {
    console.error('[CloakfoxShield] React Error:', error, errorInfo.componentStack);
    this.props.onError?.(error, errorInfo);
  }

  handleRetry = (): void => {
    this.setState({ hasError: false, error: null });
  };

  render(): ReactNode {
    if (this.state.hasError) {
      if (this.props.fallback) return this.props.fallback;

      return (
        <div className="card" style={{ borderColor: 'var(--red-border)', margin: '16px' }}>
          <div className="flex items-center gap-2 mb-2">
            <span style={{ color: 'var(--red)', fontSize: '16px' }}>!</span>
            <h3 style={{ fontWeight: 500, color: 'var(--red)', fontSize: '13px' }}>Something went wrong</h3>
          </div>
          <p style={{ fontSize: '12px', color: 'var(--text-secondary)', marginBottom: '10px' }}>
            {this.state.error?.message || 'An unexpected error occurred'}
          </p>
          <button className="btn btn-danger" onClick={this.handleRetry}>Try Again</button>
        </div>
      );
    }

    return this.props.children;
  }
}

export default ErrorBoundary;
