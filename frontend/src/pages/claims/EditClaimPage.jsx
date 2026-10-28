import { useEffect, useState } from 'react';
import { Link, useNavigate, useParams } from 'react-router';
import { Alert, Anchor, Container, Loader, Title } from '@mantine/core';

import { SchoolClaimForm } from './SchoolClaimForm';
import { actualizarReclamo, obtenerReclamo } from '../../api/reclamos';
import { notifyError, notifySuccess } from '../../utils/notifications';

export function EditClaimPage() {
  const { id } = useParams();
  const navigate = useNavigate();

  const [initialValues, setInitialValues] = useState(null);
  const [cargando, setCargando] = useState(true);
  const [errorCarga, setErrorCarga] = useState(null);

  const [guardando, setGuardando] = useState(false);

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
          phone: reclamo.telefono_creador ?? '',
        }),
      )
      .catch((err) => setErrorCarga(err.message))
      .finally(() => setCargando(false));
  }, [id]);

  const handleSubmit = async (payload) => {
    setGuardando(true);
    try {
      await actualizarReclamo(id, payload);
      notifySuccess('El reclamo fue actualizado correctamente.');
      navigate('/reclamos');
    } catch (error) {
      notifyError(error?.message);
    } finally {
      setGuardando(false);
    }
  };

  return (
    <Container size="sm" px={0}>
      <Anchor component={Link} to="/reclamos" mb="md" display="inline-block">
        ← Volver a Reclamos
      </Anchor>

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
        <SchoolClaimForm
          initialValues={initialValues}
          onSubmit={handleSubmit}
          submitting={guardando}
          submitLabel="Guardar Cambios"
        />
      )}
    </Container>
  );
}
