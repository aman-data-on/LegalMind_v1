"use client";

/**
 * One pane's failure stays in that pane (UI review item 8): a render error in the
 * document, the Summary, Points or Ask shows a calm sentence and "Try again" there,
 * and the rest of the contract page keeps working.
 */
import { Component } from "react";

export class PaneBoundary extends Component<{ what: string; children: React.ReactNode }, { failed: boolean }> {
  override state = { failed: false };

  static getDerivedStateFromError() {
    return { failed: true };
  }

  override render() {
    if (!this.state.failed) return this.props.children;
    return (
      <div className="ws-state" role="alert">
        <p>{this.props.what} could not be shown. The rest of the page still works.</p>
        <button type="button" className="ws-btn ws-btn--sm" onClick={() => this.setState({ failed: false })}>
          Try again
        </button>
      </div>
    );
  }
}
