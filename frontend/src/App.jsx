import { Navigate, Route, Routes } from 'react-router-dom';

import { AppLayout } from './layout/AppLayout';
import { ClaimsListPage } from './pages/ClaimsListPage';
import { EditClaimPage } from './pages/EditClaimPage';
import { NewClaimPage } from './pages/NewClaimPage';

function App() {
  return (
    <Routes>
      <Route element={<AppLayout />}>
        <Route index element={<Navigate to="/reclamos/nuevo" replace />} />
        <Route path="/reclamos/nuevo" element={<NewClaimPage />} />
        <Route path="/reclamos" element={<ClaimsListPage />} />
        <Route path="/reclamos/:id/editar" element={<EditClaimPage />} />
      </Route>
    </Routes>
  );
}

export default App;
