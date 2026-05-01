import React from "react";
import { AlertTriangle, RefreshCw } from "lucide-react";
import { Button } from "@/components/ui/button";

export default class ErrorBoundary extends React.Component {
  constructor(props) {
    super(props);
    this.state = { hasError: false, error: null };
  }

  static getDerivedStateFromError(error) {
    return { hasError: true, error };
  }

  componentDidCatch(error, info) {
    // eslint-disable-next-line no-console
    console.error("ErrorBoundary caught:", error, info);
  }

  reset = () => {
    this.setState({ hasError: false, error: null });
  };

  render() {
    if (this.state.hasError) {
      return (
        <div className="p-8 max-w-2xl mx-auto" data-testid="error-boundary">
          <div className="bg-card border border-destructive/30 rounded-lg p-6">
            <div className="flex items-center gap-2 text-destructive font-semibold mb-3">
              <AlertTriangle className="w-5 h-5" />
              Une erreur est survenue
            </div>
            <p className="text-sm text-muted-foreground mb-4">
              {this.state.error?.message || "Erreur inconnue"}
            </p>
            <Button onClick={this.reset} data-testid="error-retry-btn">
              <RefreshCw className="w-4 h-4 mr-2" />
              Réessayer
            </Button>
          </div>
        </div>
      );
    }
    return this.props.children;
  }
}
