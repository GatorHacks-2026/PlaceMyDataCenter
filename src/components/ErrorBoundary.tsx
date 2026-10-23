import { Component, type ErrorInfo, type ReactNode } from 'react'

interface Props {
  children: ReactNode
  fallback?: ReactNode
}

interface State {
  error: Error | null
}

/** React error boundary: isolates failures and renders a recovery view instead of crashing. */
export default class ErrorBoundary extends Component<Props, State> {
  state: State = { error: null }

  static getDerivedStateFromError(error: Error): State {
    return { error }
  }

  componentDidCatch(error: Error, info: ErrorInfo) {
    console.error('ErrorBoundary caught:', error, info.componentStack)
  }

  render() {
    const { error } = this.state
    if (!error) return this.props.children

    if (this.props.fallback) {
      return this.props.fallback
    }

    return (
      <div className="flex min-h-screen items-center justify-center bg-navy-900 p-6 text-slate-200">
        <div className="w-full max-w-xl rounded-xl border border-red-500/40 bg-navy-800 p-6 shadow-xl">
          <div className="flex items-center gap-2">
            <span className="flex h-3 w-3 rounded-full bg-red-400" />
            <h2 className="text-lg font-semibold text-red-300">
              Application Encountered an Error
            </h2>
          </div>
          <pre className="mt-3 max-h-48 overflow-auto rounded-lg bg-navy-900 p-3 font-mono text-xs text-red-200/90 whitespace-pre-wrap">
            {error.message}
          </pre>
          <div className="mt-5 flex gap-3">
            <button
              onClick={() => this.setState({ error: null })}
              className="rounded-lg bg-teal-accent px-4 py-2 text-xs font-semibold text-navy-900 transition-opacity hover:opacity-90"
            >
              Try again
            </button>
            <button
              onClick={() => window.location.reload()}
              className="rounded-lg border border-navy-600 bg-navy-700 px-4 py-2 text-xs font-semibold text-slate-200 transition-colors hover:border-slate-500"
            >
              Reload application
            </button>
          </div>
        </div>
      </div>
    )
  }
}
