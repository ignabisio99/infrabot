import { Navigate, Route, Routes } from 'react-router-dom';

import { AppLayout } from './layout/AppLayout';
import { ClaimsListPage } from './pages/ClaimsListPage';
import { ContractorsListPage } from './pages/ContractorsListPage';
import { EditClaimPage } from './pages/EditClaimPage';
import { EditContractorPage } from './pages/EditContractorPage';
import { NewClaimPage } from './pages/NewClaimPage';
import { NewContractorPage } from './pages/NewContractorPage';

function App() {
  return (
    <Routes>
      <Route element={<AppLayout />}>
        <Route index element={<Navigate to="/reclamos" replace />} />
        <Route path="/reclamos/nuevo" element={<NewClaimPage />} />
        <Route path="/reclamos" element={<ClaimsListPage />} />
        <Route path="/reclamos/:id/editar" element={<EditClaimPage />} />
        <Route path="/contratistas/nuevo" element={<NewContractorPage />} />
        <Route path="/contratistas" element={<ContractorsListPage />} />
        <Route path="/contratistas/:id/editar" element={<EditContractorPage />} />
      </Route>
    </Routes>
  );
}

export default App;
