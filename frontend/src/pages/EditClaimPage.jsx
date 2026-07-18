import { useEffect, useState } from 'react';
import { useNavigate, useParams } from 'react-router-dom';
import { Alert, Container, Loader, Title } from '@mantine/core';

import { SchoolClaimForm } from '../components/forms/SchoolClaimForm';
import { actualizarReclamo, obtenerReclamo } from '../api/reclamos';

export function EditClaimPage() {
  const { id } = useParams();
  const navigate = useNavigate();

  const [initialValues, setInitialValues] = useState(null);
  const [cargando, setCargando] = useState(true);
  const [errorCarga, setErrorCarga] = useState(null);

  const [guardando, setGuardando] = useState(false);
  const [errorGuardado, setErrorGuardado] = useState(null);

  useEffect(() => {
    obtenerReclamo(id)
      .then((reclamo) =>
        setInitialValues({
          schoolName: reclamo.nombre_escuela,
          sector: reclamo.ubicacion,
          priority: reclamo.prioridad,
          category: reclamo.categoria,
          description: reclamo.descripcion,
          observations: reclamo.observaciones ?? '',
        }),
      )
      .catch((err) => setErrorCarga(err.message))
      .finally(() => setCargando(false));
  }, [id]);

  const handleSubmit = async (payload) => {
    setErrorGuardado(null);
    setGuardando(true);
    try {
      await actualizarReclamo(id, payload);
      navigate('/reclamos');
    } catch (err) {
      setErrorGuardado(err.message);
    } finally {
      setGuardando(false);
    }
  };

  return (
    <Container size="sm" py="xl">
      <Title order={2} mb="md">
        Editar Reclamo
      </Title>

      {cargando && <Loader />}

      {errorCarga && (
        <Alert color="red" title="No se pudo cargar el reclamo">
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
          <SchoolClaimForm
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
