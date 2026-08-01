import { BrowserRouter, Navigate, Route, Routes } from 'react-router-dom';
import { Capture } from './pages/Capture';
import { Chart } from './pages/Chart';
import { Home } from './pages/Home';
import { Review } from './pages/Review';
import { Trust } from './pages/Trust';

export default function App() {
  return (
    <BrowserRouter>
      <Routes>
        <Route path="/" element={<Home />} />
        <Route path="/capture/:token" element={<Capture />} />
        <Route path="/chart/:encounterId" element={<Chart />} />
        <Route path="/review" element={<Review />} />
        <Route path="/trust" element={<Trust />} />
        <Route path="*" element={<Navigate to="/" replace />} />
      </Routes>
    </BrowserRouter>
  );
}
