import { useState } from 'react';
import { Navigate, Route, Routes } from 'react-router-dom';

import { AppLayout } from './layout/AppLayout';
import { ConfirmarEmailPage } from './pages/auth/ConfirmarEmailPage';
import { LoginPage } from './pages/auth/LoginPage';
import { BudgetsListPage } from './pages/budgets/BudgetsListPage';
import { EditBudgetPage } from './pages/budgets/EditBudgetPage';
import { NewBudgetPage } from './pages/budgets/NewBudgetPage';
import { CalendarPage } from './pages/calendar/CalendarPage';
import { ClaimsListPage } from './pages/claims/ClaimsListPage';
import { EditClaimPage } from './pages/claims/EditClaimPage';
import { NewClaimPage } from './pages/claims/NewClaimPage';
import { ContractorsListPage } from './pages/contractors/ContractorsListPage';
import { EditContractorPage } from './pages/contractors/EditContractorPage';
import { NewContractorPage } from './pages/contractors/NewContractorPage';
import { DashboardPage } from './pages/dashboard/DashboardPage';
import { ReportsPage } from './pages/reports/ReportsPage';
import { SettingsPage } from './pages/settings/SettingsPage';

function App() {
  const [autenticado, setAutenticado] = useState(() => {
    return !!localStorage.getItem('infrabot_user');
  });

  if (!autenticado) {
    return (
      <Routes>
        <Route path="/confirmar" element={<ConfirmarEmailPage />} />
        <Route path="*" element={<LoginPage onLogin={() => setAutenticado(true)} />} />
      </Routes>
    );
  }

  return (
    <Routes>
      <Route element={<AppLayout />}>
        <Route index element={<Navigate to="/reclamos" replace />} />
        <Route path="/dashboard" element={<DashboardPage />} />
        <Route path="/reclamos/nuevo" element={<NewClaimPage />} />
        <Route path="/reclamos" element={<ClaimsListPage />} />
        <Route path="/reclamos/:id/editar" element={<EditClaimPage />} />
        <Route path="/contratistas/nuevo" element={<NewContractorPage />} />
        <Route path="/contratistas" element={<ContractorsListPage />} />
        <Route path="/contratistas/:id/editar" element={<EditContractorPage />} />
        <Route path="/presupuestos/nuevo" element={<NewBudgetPage />} />
        <Route path="/presupuestos" element={<BudgetsListPage />} />
        <Route path="/presupuestos/:id/editar" element={<EditBudgetPage />} />
        <Route path="/calendario" element={<CalendarPage />} />
        <Route path="/reportes" element={<ReportsPage />} />
        <Route path="/configuracion" element={<SettingsPage />} />
      </Route>
    </Routes>
  );
}

export default App;
