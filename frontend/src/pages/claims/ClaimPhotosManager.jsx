import { useState } from 'react';
import { Image, Modal, Text } from '@mantine/core';

import { API_URL } from '../../api/apiClient';
import { eliminarFotoReclamo, subirFotoReclamo } from '../../api/reclamos';
import { notifyError } from '../../utils/notifications';
import { PhotoDropzone } from './PhotoDropzone';
import { PhotoGrid } from './PhotoGrid';

function isVideo(item) {
  return item.tipo === 'VIDEO' || /\.(mp4|mov|webm|3gp)$/i.test(item.src);
}

export function ClaimPhotosManager({ reclamoId, fotosIniciales = [], soloLectura = false }) {
  const [fotos, setFotos] = useState(fotosIniciales);
  const [subiendo, setSubiendo] = useState(false);
  const [eliminandoId, setEliminandoId] = useState(null);
  const [mediaAmpliada, setMediaAmpliada] = useState(null);

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
    tipo: foto.tipo,
  }));

  return (
    <div>
      {!soloLectura && (
        <PhotoDropzone
          onDrop={handleDrop}
          loading={subiendo}
          helperText="JPG, PNG, WEBP, MP4, MOV o WEBM — hasta 50MB cada uno"
        />
      )}

      {soloLectura && items.length === 0 && (
        <Text c="dimmed" size="sm">
          Este reclamo no tiene fotos ni videos.
        </Text>
      )}

      <PhotoGrid
        items={items}
        onRemove={soloLectura ? undefined : handleEliminar}
        onSelect={setMediaAmpliada}
        removingId={eliminandoId}
      />

      <Modal
        opened={mediaAmpliada !== null}
        onClose={() => setMediaAmpliada(null)}
        title={mediaAmpliada?.alt}
        size="xl"
        centered
      >
        {mediaAmpliada && isVideo(mediaAmpliada) ? (
          <video
            src={mediaAmpliada.src}
            controls
            autoPlay
            style={{ width: '100%', maxHeight: '70vh', borderRadius: 8 }}
          />
        ) : (
          <Image
            src={mediaAmpliada?.src}
            alt={mediaAmpliada?.alt}
            radius="md"
            w="100%"
            fit="contain"
            style={{ maxHeight: '70vh' }}
          />
        )}
      </Modal>
    </div>
  );
}
