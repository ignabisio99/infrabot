import { useEffect, useState } from 'react';
import { Link, useNavigate, useParams } from 'react-router-dom';
import { Alert, Anchor, Container, Loader, Title } from '@mantine/core';

import { BudgetForm } from './BudgetForm';
import { actualizarPresupuesto, obtenerPresupuesto } from '../../api/presupuestos';
import { listarReclamos } from '../../api/reclamos';
import { listarContratistas } from '../../api/contratistas';
import { notifyError, notifySuccess } from '../../utils/notifications';
import { partirItems } from '../../utils/presupuestoItems';

export function EditBudgetPage() {
  const { id } = useParams();
  const navigate = useNavigate();

  const [reclamos, setReclamos] = useState([]);
  const [contratistas, setContratistas] = useState([]);
  const [initialValues, setInitialValues] = useState(null);
  const [cargando, setCargando] = useState(true);
  const [errorCarga, setErrorCarga] = useState(null);

  const [guardando, setGuardando] = useState(false);

  useEffect(() => {
    Promise.all([obtenerPresupuesto(id), listarReclamos(), listarContratistas()])
      .then(([presupuesto, reclamosData, contratistasData]) => {
        setReclamos(reclamosData);
        setContratistas(contratistasData);
        const { materials, labor } = partirItems(presupuesto.items);
        setInitialValues({
          claimId: String(presupuesto.reclamo_id),
          contractorId: String(presupuesto.contratista_id),
          taskDetail: presupuesto.detalle_tarea ?? '',
          notes: presupuesto.observaciones ?? '',
          materials,
          labor,
        });
      })
      .catch((err) => setErrorCarga(err.message))
      .finally(() => setCargando(false));
  }, [id]);

  const handleSubmit = async (payload) => {
    setGuardando(true);
    try {
      await actualizarPresupuesto(id, payload);
      notifySuccess('El presupuesto fue actualizado correctamente.');
      navigate('/presupuestos');
    } catch (error) {
      notifyError(error?.message);
    } finally {
      setGuardando(false);
    }
  };

  return (
    <Container size="md" px={0}>
      <Anchor component={Link} to="/presupuestos" mb="md" display="inline-block">
        ← Volver a Presupuestos
      </Anchor>

      <Title order={2} mb="md">
        Editar Presupuesto
      </Title>

      {cargando && <Loader />}

      {errorCarga && (
        <Alert color="red" title="No se pudo cargar el presupuesto">
          {errorCarga}
        </Alert>
      )}

      {!cargando && !errorCarga && initialValues && (
        <>
          <BudgetForm
            reclamosDisponibles={reclamos}
            contratistasDisponibles={contratistas}
            initialValues={initialValues}
            onSubmit={handleSubmit}
            submitting={guardando}
            submitLabel="Guardar Cambios"
            reclamoEditable={false}
          />
        </>
      )}
    </Container>
  );
}
