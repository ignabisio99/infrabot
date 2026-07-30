import { useState } from 'react';
import { Image, Modal } from '@mantine/core';

import { API_URL } from '../../api/apiClient';
import { eliminarFotoReclamo, subirFotoReclamo } from '../../api/reclamos';
import { notifyError } from '../../utils/notifications';
import { PhotoDropzone } from './PhotoDropzone';
import { PhotoGrid } from './PhotoGrid';

export function ClaimPhotosManager({ reclamoId, fotosIniciales = [] }) {
  const [fotos, setFotos] = useState(fotosIniciales);
  const [subiendo, setSubiendo] = useState(false);
  const [eliminandoId, setEliminandoId] = useState(null);
  const [fotoAmpliada, setFotoAmpliada] = useState(null);

  const handleDrop = async (archivos) => {
    setSubiendo(true);
    try {
      for (const archivo of archivos) {
        const foto = await subirFotoReclamo(reclamoId, archivo);
        setFotos((actuales) => [...actuales, foto]);
      }
    } catch (error) {
      notifyError(error?.message);
    } finally {
      setSubiendo(false);
    }
  };

  const handleEliminar = async (fotoId) => {
    setEliminandoId(fotoId);
    try {
      await eliminarFotoReclamo(reclamoId, fotoId);
      setFotos((actuales) => actuales.filter((foto) => foto.id !== fotoId));
    } catch (error) {
      notifyError(error?.message);
    } finally {
      setEliminandoId(null);
    }
  };

  const items = fotos.map((foto) => ({
    id: foto.id,
    src: `${API_URL}${foto.url}`,
    alt: foto.nombre_archivo,
  }));

  return (
    <div>
      <PhotoDropzone
        onDrop={handleDrop}
        loading={subiendo}
        helperText="JPG, PNG o WEBP, hasta 5MB cada una"
      />

      <PhotoGrid
        items={items}
        onRemove={handleEliminar}
        onSelect={setFotoAmpliada}
        removingId={eliminandoId}
      />

      <Modal
        opened={fotoAmpliada !== null}
        onClose={() => setFotoAmpliada(null)}
        title={fotoAmpliada?.alt}
        size="lg"
      >
        <div style={{ aspectRatio: '16 / 10' }}>
          <Image
            src={fotoAmpliada?.src}
            alt={fotoAmpliada?.alt}
            radius="md"
            h="100%"
            w="100%"
            fit="cover"
          />
        </div>
      </Modal>
    </div>
  );
}
