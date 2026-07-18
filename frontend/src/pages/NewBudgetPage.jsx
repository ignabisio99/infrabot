import { useEffect, useState } from 'react';
import { Link } from 'react-router-dom';
import { Alert, Anchor, Container, Loader } from '@mantine/core';

import { BudgetForm } from '../components/forms/BudgetForm';
import { crearPresupuesto } from '../api/presupuestos';
import { listarReclamos } from '../api/reclamos';
import { listarContratistas } from '../api/contratistas';

export function NewBudgetPage() {
  const [reclamos, setReclamos] = useState([]);
  const [contratistas, setContratistas] = useState([]);
  const [cargandoDatos, setCargandoDatos] = useState(true);
  const [errorDatos, setErrorDatos] = useState(null);

  const [enviando, setEnviando] = useState(false);
  const [error, setError] = useState(null);
  const [enviadoOk, setEnviadoOk] = useState(false);
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
    setError(null);
    setEnviadoOk(false);
    setEnviando(true);
    try {
      await crearPresupuesto(payload);
      setEnviadoOk(true);
      setFormKey((key) => key + 1);
    } catch (err) {
      setError(err.message);
    } finally {
      setEnviando(false);
    }
  };

  return (
    <Container size="md" py="xl">
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
          {error && (
            <Alert color="red" title="No se pudo guardar el presupuesto" mb="md">
              {error}
            </Alert>
          )}

          {enviadoOk && (
            <Alert color="green" title="Presupuesto guardado" mb="md">
              El presupuesto fue registrado correctamente.
            </Alert>
          )}

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
