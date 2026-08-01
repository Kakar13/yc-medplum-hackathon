import { BrowserRouter, Navigate, Route, Routes } from 'react-router-dom';
import { Capture } from './pages/Capture';
import { Chart } from './pages/Chart';
import { Home } from './pages/Home';

export default function App() {
  return (
    <BrowserRouter>
      <Routes>
        <Route path="/" element={<Home />} />
        <Route path="/capture/:token" element={<Capture />} />
        <Route path="/chart/:encounterId" element={<Chart />} />
        <Route path="*" element={<Navigate to="/" replace />} />
      </Routes>
    </BrowserRouter>
  );
}
