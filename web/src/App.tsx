import { BrowserRouter, Navigate, Route, Routes } from 'react-router-dom';
import { WorkspaceProvider } from './workspace/Workspace';
import { PreferencesProvider } from './workspace/Preferences';
import { WorkspaceShell } from './workspace/WorkspaceShell';
import { OverviewPage } from './pages/OverviewPage';
import { ReviewPage } from './pages/ReviewPage';
import { ProofPage } from './pages/ProofPage';
import { ActivityPage } from './pages/ActivityPage';
import { SettingsPage } from './pages/SettingsPage';
import { NotFound } from './pages/NotFound';

/** URL-addressable workspaces keep sample and API-backed state in separate lifecycles. */
export function AppRoutes() {
  return (
    <Routes>
      <Route path="/" element={<Navigate to="/sample/overview" replace />} />
      <Route path="/review" element={<Navigate to="/workspace/review" replace />} />
      <Route path="/proofs" element={<Navigate to="/workspace/proofs" replace />} />
      {(['sample', 'workspace'] as const).map((prefix) => (
        <Route
          key={prefix}
          path={`/${prefix}`}
          element={
            <WorkspaceProvider key={prefix} mode={prefix === 'sample' ? 'sample' : 'connected'}>
              <WorkspaceShell />
            </WorkspaceProvider>
          }
        >
          <Route index element={<Navigate to="overview" replace />} />
          <Route path="overview" element={<OverviewPage />} />
          <Route path="review/:proposalId?" element={<ReviewPage />} />
          <Route path="proofs" element={<ProofPage />} />
          <Route path="activity" element={<ActivityPage />} />
          <Route path="settings" element={<SettingsPage />} />
          <Route path="*" element={<NotFound />} />
        </Route>
      ))}
      <Route path="*" element={<NotFound />} />
    </Routes>
  );
}
export default function App() {
  return (
    <BrowserRouter>
      <PreferencesProvider>
        <AppRoutes />
      </PreferencesProvider>
    </BrowserRouter>
  );
}
