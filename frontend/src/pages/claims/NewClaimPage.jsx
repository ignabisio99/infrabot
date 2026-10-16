import { useState } from 'react';
import { Link } from 'react-router';
import { Anchor, Container, Title } from '@mantine/core';

import { SchoolClaimForm } from './SchoolClaimForm';
import { StagedPhotosPicker } from './StagedPhotosPicker';
import { crearReclamo, subirFotoReclamo } from '../../api/reclamos';
import { notifyError, notifySuccess } from '../../utils/notifications';

export function NewClaimPage() {
  const [enviando, setEnviando] = useState(false);
  const [formKey, setFormKey] = useState(0);
  const [fotosPendientes, setFotosPendientes] = useState([]);

  const handleSubmit = async (payload) => {
    setEnviando(true);
    try {
      const reclamo = await crearReclamo(payload);

      let fotosFallidas = 0;
      for (const { file } of fotosPendientes) {
        try {
          await subirFotoReclamo(reclamo.id, file);
        } catch {
          fotosFallidas += 1;
        }
      }

      if (fotosFallidas > 0) {
        notifyError(
          `El reclamo fue registrado, pero ${fotosFallidas} foto(s) no se pudieron subir.`,
        );
      } else {
        notifySuccess('Tu reclamo fue registrado. La IA ya lo clasificó y estimó en segundo plano.');
      }

      setFotosPendientes([]);
      setFormKey((key) => key + 1);
    } catch (error) {
      notifyError(error?.message);
    } finally {
      setEnviando(false);
    }
  };

  return (
    <Container size="sm" px={0}>
      <Anchor component={Link} to="/reclamos" mb="md" display="inline-block">
        ← Volver a Reclamos
      </Anchor>

      <SchoolClaimForm key={formKey} onSubmit={handleSubmit} submitting={enviando}>
        <div>
          <Title order={5} mb={4}>
            Fotos (opcional)
          </Title>
          <StagedPhotosPicker archivos={fotosPendientes} onChange={setFotosPendientes} />
        </div>
      </SchoolClaimForm>
    </Container>
  );
}
