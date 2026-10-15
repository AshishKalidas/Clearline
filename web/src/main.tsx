import React from 'react';
import ReactDOM from 'react-dom/client';
import App from './App';
import { restoreAppearance } from './workspace/Preferences';
import './styles.css';

restoreAppearance();
ReactDOM.createRoot(document.getElementById('root')!).render(
  <React.StrictMode>
    <App />
  </React.StrictMode>,
);
