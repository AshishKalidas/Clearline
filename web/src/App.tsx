import { BrowserRouter, Navigate, Route, Routes, useLocation } from 'react-router-dom';
import { isDemoDeployment } from './deployment';
import { WorkspaceProvider } from './workspace/Workspace';
import { PreferencesProvider } from './workspace/Preferences';
import { WorkspaceShell } from './workspace/WorkspaceShell';
import { OverviewPage } from './pages/OverviewPage';
import { ReviewPage } from './pages/ReviewPage';
import { ProofPage } from './pages/ProofPage';
import { ActivityPage } from './pages/ActivityPage';
import { SettingsPage } from './pages/SettingsPage';
import { NotFound } from './pages/NotFound';
import { ImportPage } from './pages/ImportPage';
import { EvaluationPage } from './pages/EvaluationPage';

/** URL-addressable workspaces keep sample and API-backed state in separate lifecycles. */
export function AppRoutes() {
  const demo = isDemoDeployment();
  const prefixes = demo ? (['sample'] as const) : (['sample', 'workspace'] as const);
  return (
    <Routes>
      <Route path="/" element={<Navigate to="/sample/overview" replace />} />
      <Route
        path="/review"
        element={<Navigate to={demo ? '/sample/review' : '/workspace/review'} replace />}
      />
      <Route
        path="/proofs"
        element={<Navigate to={demo ? '/sample/proofs' : '/workspace/proofs'} replace />}
      />
      {demo && <Route path="/workspace/*" element={<DemoRedirect />} />}
      {prefixes.map((prefix) => (
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
          <Route path="import" element={<ImportPage />} />
          <Route path="evaluation" element={<EvaluationPage />} />
          <Route path="*" element={<NotFound />} />
        </Route>
      ))}
      <Route path="*" element={<NotFound />} />
    </Routes>
  );
}

function DemoRedirect() {
  const { pathname, search, hash } = useLocation();
  return <Navigate to={`${pathname.replace(/^\/workspace/, '/sample')}${search}${hash}`} replace />;
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
