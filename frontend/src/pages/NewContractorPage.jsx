import { useState } from 'react';
import { Link } from 'react-router-dom';
import { Alert, Anchor, Container } from '@mantine/core';

import { ContractorForm } from '../components/forms/ContractorForm';
import { crearContratista } from '../api/contratistas';

export function NewContractorPage() {
  const [enviando, setEnviando] = useState(false);
  const [error, setError] = useState(null);
  const [enviadoOk, setEnviadoOk] = useState(false);
  const [formKey, setFormKey] = useState(0);

  const handleSubmit = async (payload) => {
    setError(null);
    setEnviadoOk(false);
    setEnviando(true);
    try {
      await crearContratista(payload);
      setEnviadoOk(true);
      setFormKey((key) => key + 1);
    } catch (err) {
      setError(err.message);
    } finally {
      setEnviando(false);
    }
  };

  return (
    <Container size="sm" py="xl">
      <Anchor component={Link} to="/contratistas" mb="md" display="inline-block">
        ← Volver a Contratistas
      </Anchor>

      {error && (
        <Alert color="red" title="No se pudo guardar el contratista" mb="md">
          {error}
        </Alert>
      )}

      {enviadoOk && (
        <Alert color="green" title="Contratista guardado" mb="md">
          El contratista fue registrado correctamente.
        </Alert>
      )}

      <ContractorForm key={formKey} onSubmit={handleSubmit} submitting={enviando} />
    </Container>
  );
}
