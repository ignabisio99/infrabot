import { useEffect, useState } from 'react';
import { Link, useNavigate, useParams } from 'react-router-dom';
import { Alert, Anchor, Container, Loader, Title } from '@mantine/core';

import { BudgetForm } from '../components/forms/BudgetForm';
import { actualizarPresupuesto, obtenerPresupuesto } from '../api/presupuestos';
import { listarReclamos } from '../api/reclamos';
import { listarContratistas } from '../api/contratistas';

export function EditBudgetPage() {
  const { id } = useParams();
  const navigate = useNavigate();

  const [reclamos, setReclamos] = useState([]);
  const [contratistas, setContratistas] = useState([]);
  const [initialValues, setInitialValues] = useState(null);
  const [cargando, setCargando] = useState(true);
  const [errorCarga, setErrorCarga] = useState(null);

  const [guardando, setGuardando] = useState(false);
  const [errorGuardado, setErrorGuardado] = useState(null);

  useEffect(() => {
    Promise.all([obtenerPresupuesto(id), listarReclamos(), listarContratistas()])
      .then(([presupuesto, reclamosData, contratistasData]) => {
        setReclamos(reclamosData);
        setContratistas(contratistasData);
        setInitialValues({
          claimId: String(presupuesto.reclamo_id),
          contractorId: String(presupuesto.contratista_id),
          notes: presupuesto.observaciones ?? '',
          items: presupuesto.items.map((item) => ({
            description: item.descripcion,
            quantity: item.cantidad,
            unitCost: item.costo_unitario,
          })),
        });
      })
      .catch((err) => setErrorCarga(err.message))
      .finally(() => setCargando(false));
  }, [id]);

  const handleSubmit = async (payload) => {
    setErrorGuardado(null);
    setGuardando(true);
    try {
      await actualizarPresupuesto(id, payload);
      navigate('/presupuestos');
    } catch (err) {
      setErrorGuardado(err.message);
    } finally {
      setGuardando(false);
    }
  };

  return (
    <Container size="md" py="xl">
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
          {errorGuardado && (
            <Alert color="red" title="No se pudo guardar" mb="md">
              {errorGuardado}
            </Alert>
          )}
          <BudgetForm
            reclamosDisponibles={reclamos}
            contratistasDisponibles={contratistas}
            initialValues={initialValues}
            onSubmit={handleSubmit}
            submitting={guardando}
            submitLabel="Guardar Cambios"
          />
        </>
      )}
    </Container>
  );
}
