import { Navigate, Route, Routes } from 'react-router-dom';

import { AppLayout } from './layout/AppLayout';
import { BudgetsListPage } from './pages/budgets/BudgetsListPage';
import { EditBudgetPage } from './pages/budgets/EditBudgetPage';
import { NewBudgetPage } from './pages/budgets/NewBudgetPage';
import { ClaimsListPage } from './pages/claims/ClaimsListPage';
import { EditClaimPage } from './pages/claims/EditClaimPage';
import { NewClaimPage } from './pages/claims/NewClaimPage';
import { ContractorsListPage } from './pages/contractors/ContractorsListPage';
import { EditContractorPage } from './pages/contractors/EditContractorPage';
import { NewContractorPage } from './pages/contractors/NewContractorPage';

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
        <Route path="/presupuestos/nuevo" element={<NewBudgetPage />} />
        <Route path="/presupuestos" element={<BudgetsListPage />} />
        <Route path="/presupuestos/:id/editar" element={<EditBudgetPage />} />
      </Route>
    </Routes>
  );
}

export default App;
