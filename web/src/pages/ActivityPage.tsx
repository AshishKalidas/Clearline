import { LivePanel } from '../workspace/LivePanel';
import { PageHeader } from '../workspace/PageHeader';
import { useWorkspace } from '../workspace/Workspace';
export function ActivityPage() {
  const { mode } = useWorkspace();
  return (
    <>
      <PageHeader
        eyebrow="Nothing happens without a trace"
        title="A clearer picture. As it happens."
        description={
          mode === 'sample'
            ? 'Illustrative events update when you review a sample payment.'
            : 'The latest 20 audited decisions and proof checks, refreshed from your API.'
        }
      />
      <LivePanel expanded />
    </>
  );
}
