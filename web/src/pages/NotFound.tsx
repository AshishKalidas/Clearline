import { Link, useLocation } from 'react-router-dom';
import { Icon } from '../Icon';
export function NotFound() {
  const { pathname } = useLocation();
  const base = pathname.startsWith('/workspace/') ? '/workspace' : '/sample';
  return (
    <section className="not-found panel">
      <Icon name="search" size={36} />
      <span className="eyebrow">404 · Page not found</span>
      <h1>A small wrong turn.</h1>
      <p>This page doesn’t exist. Your workspace is right here.</p>
      <Link className="primary-button" to={`${base}/overview`}>
        Back to overview <Icon name="arrow" size={17} />
      </Link>
    </section>
  );
}
