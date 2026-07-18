import { useEffect, useState } from 'react';
import { Link, useNavigate, useParams } from 'react-router-dom';
import { Alert, Anchor, Container, Loader, Title } from '@mantine/core';

import { ContractorForm } from '../components/forms/ContractorForm';
import { actualizarContratista, obtenerContratista } from '../api/contratistas';

export function EditContractorPage() {
  const { id } = useParams();
  const navigate = useNavigate();

  const [initialValues, setInitialValues] = useState(null);
  const [cargando, setCargando] = useState(true);
  const [errorCarga, setErrorCarga] = useState(null);

  const [guardando, setGuardando] = useState(false);
  const [errorGuardado, setErrorGuardado] = useState(null);

  useEffect(() => {
    obtenerContratista(id)
      .then((contratista) =>
        setInitialValues({
          companyName: contratista.nombre_empresa,
          phone: contratista.telefono,
          address: contratista.direccion,
          specialty: contratista.especialidad,
          rating: contratista.calificacion,
        }),
      )
      .catch((err) => setErrorCarga(err.message))
      .finally(() => setCargando(false));
  }, [id]);

  const handleSubmit = async (payload) => {
    setErrorGuardado(null);
    setGuardando(true);
    try {
      await actualizarContratista(id, payload);
      navigate('/contratistas');
    } catch (err) {
      setErrorGuardado(err.message);
    } finally {
      setGuardando(false);
    }
  };

  return (
    <Container size="sm" py="xl">
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
          {errorGuardado && (
            <Alert color="red" title="No se pudo guardar" mb="md">
              {errorGuardado}
            </Alert>
          )}
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
