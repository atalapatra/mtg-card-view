import { StrictMode } from 'react';
import { createRoot } from 'react-dom/client';
import App from './App';
import { PreviewProvider } from './components/HoverPreview';
import './styles.css';

createRoot(document.getElementById('root')!).render(
  <StrictMode>
    <PreviewProvider>
      <App />
    </PreviewProvider>
  </StrictMode>,
);
