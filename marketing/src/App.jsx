import { useEffect } from 'react';
import { BrowserRouter, Routes, Route, useLocation } from 'react-router-dom';
import LandingPage from './pages/LandingPage.jsx';
import FutureVisionPage from './pages/FutureVisionPage.jsx';

// Route changes don't reset scroll on their own — a same-page "#anchor"
// link should still scroll smoothly within the page, but landing on a new
// route (clicking "Future Vision") should start at the top of it.
function ScrollToTop() {
  const { pathname, hash } = useLocation();
  useEffect(() => {
    if (!hash) window.scrollTo(0, 0);
  }, [pathname, hash]);
  return null;
}

export default function App() {
  return (
    <BrowserRouter>
      <ScrollToTop />
      <Routes>
        <Route path="/" element={<LandingPage />} />
        <Route path="/future-vision" element={<FutureVisionPage />} />
      </Routes>
    </BrowserRouter>
  );
}
