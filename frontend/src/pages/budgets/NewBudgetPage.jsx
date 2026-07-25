import { useEffect, useState } from 'react';
import { Link } from 'react-router-dom';
import { Alert, Anchor, Container, Loader } from '@mantine/core';

import { BudgetForm } from './BudgetForm';
import { crearPresupuesto } from '../../api/presupuestos';
import { listarReclamos } from '../../api/reclamos';
import { listarContratistas } from '../../api/contratistas';
import { notifyError, notifySuccess } from '../../utils/notifications';

export function NewBudgetPage() {
  const [reclamos, setReclamos] = useState([]);
  const [contratistas, setContratistas] = useState([]);
  const [cargandoDatos, setCargandoDatos] = useState(true);
  const [errorDatos, setErrorDatos] = useState(null);

  const [enviando, setEnviando] = useState(false);
  const [formKey, setFormKey] = useState(0);

  useEffect(() => {
    Promise.all([listarReclamos(), listarContratistas()])
      .then(([reclamosData, contratistasData]) => {
        setReclamos(reclamosData);
        setContratistas(contratistasData);
      })
      .catch((err) => setErrorDatos(err.message))
      .finally(() => setCargandoDatos(false));
  }, []);

  const handleSubmit = async (payload) => {
    setEnviando(true);
    try {
      await crearPresupuesto(payload);
      notifySuccess('El presupuesto fue registrado correctamente.');
      setFormKey((key) => key + 1);
    } catch (error) {
      notifyError(error?.message);
    } finally {
      setEnviando(false);
    }
  };

  return (
    <Container size="md" px={0}>
      <Anchor component={Link} to="/presupuestos" mb="md" display="inline-block">
        ← Volver a Presupuestos
      </Anchor>

      {cargandoDatos && <Loader />}

      {errorDatos && (
        <Alert color="red" title="No se pudieron cargar los datos">
          {errorDatos}
        </Alert>
      )}

      {!cargandoDatos && !errorDatos && (
        <>
          <BudgetForm
            key={formKey}
            reclamosDisponibles={reclamos}
            contratistasDisponibles={contratistas}
            onSubmit={handleSubmit}
            submitting={enviando}
          />
        </>
      )}
    </Container>
  );
}
