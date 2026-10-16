import { useEffect, useState } from 'react';
import { Link, useNavigate, useParams } from 'react-router';
import { Alert, Anchor, Container, Loader, Title } from '@mantine/core';

import { ContractorForm } from './ContractorForm';
import { actualizarContratista, obtenerContratista } from '../../api/contratistas';
import { notifyError, notifySuccess } from '../../utils/notifications';

export function EditContractorPage() {
  const { id } = useParams();
  const navigate = useNavigate();

  const [initialValues, setInitialValues] = useState(null);
  const [cargando, setCargando] = useState(true);
  const [errorCarga, setErrorCarga] = useState(null);

  const [guardando, setGuardando] = useState(false);

  useEffect(() => {
    obtenerContratista(id)
      .then((contratista) =>
        setInitialValues({
          companyName: contratista.nombre_empresa,
          phone: contratista.telefono,
          address: contratista.direccion,
          specialty: contratista.especialidad,
          // El Select trabaja con strings; null/N/A queda como '' (sin selección).
          rating: contratista.calificacion != null ? String(contratista.calificacion) : '',
          ratingNotes: contratista.observaciones_calificacion ?? '',
        }),
      )
      .catch((err) => setErrorCarga(err.message))
      .finally(() => setCargando(false));
  }, [id]);

  const handleSubmit = async (payload) => {
    setGuardando(true);
    try {
      await actualizarContratista(id, payload);
      notifySuccess('El contratista fue actualizado correctamente.');
      navigate('/contratistas');
    } catch (error) {
      notifyError(error?.message);
    } finally {
      setGuardando(false);
    }
  };

  return (
    <Container size="sm" px={0}>
      <Anchor component={Link} to="/contratistas" mb="md" display="inline-block">
        ← Volver a Contratistas
      </Anchor>

      <Title order={2} mb="md">
        Editar Contratista
      </Title>

      {cargando && <Loader />}

      {errorCarga && (
        <Alert color="red" title="No se pudo cargar el contratista">
          {errorCarga}
        </Alert>
      )}

      {!cargando && !errorCarga && initialValues && (
        <>
          <ContractorForm
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
