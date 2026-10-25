import { useState } from 'react';
import { Button, Group, Image, Modal, Text } from '@mantine/core';

import { API_URL } from '../../api/apiClient';
import { eliminarFotoReclamo, subirFotoReclamo } from '../../api/reclamos';
import { notifyError } from '../../utils/notifications';
import { PhotoDropzone } from './PhotoDropzone';
import { PhotoGrid } from './PhotoGrid';

function isVideo(item) {
  return item.tipo === 'VIDEO' || /\.(mp4|mov|webm|3gp)$/i.test(item.src);
}

// `soloLectura` saca subida y borrado; `puedeSubir` y `puedeEliminarFoto` los habilitan
// igual (caso inspector: sube y quita sólo las suyas).
export function ClaimPhotosManager({
  reclamoId,
  fotosIniciales = [],
  soloLectura = false,
  puedeSubir = !soloLectura,
  puedeEliminarFoto = () => !soloLectura,
  onFotoEliminada,
  onFotoSubida,
}) {
  const [fotos, setFotos] = useState(fotosIniciales);
  const [subiendo, setSubiendo] = useState(false);
  const [eliminandoId, setEliminandoId] = useState(null);
  const [mediaAmpliada, setMediaAmpliada] = useState(null);
  const [fotoAEliminar, setFotoAEliminar] = useState(null);

  const handleDrop = async (archivos) => {
    setSubiendo(true);
    try {
      for (const archivo of archivos) {
        const foto = await subirFotoReclamo(reclamoId, archivo);
        setFotos((actuales) => [...actuales, foto]);
        onFotoSubida?.(foto);
      }
    } catch (error) {
      notifyError(error?.message);
    } finally {
      setSubiendo(false);
    }
  };

  const handleEliminar = async (fotoId) => {
    setFotoAEliminar(null);
    setEliminandoId(fotoId);
    try {
      await eliminarFotoReclamo(reclamoId, fotoId);
      setFotos((actuales) => actuales.filter((foto) => foto.id !== fotoId));
      onFotoEliminada?.(fotoId);
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
    // Solo los inspectores suben fotos al reclamo: se firma "Ana (inspector)". Las que
    // cargó el admin al crear el reclamo son las de la escuela y van sin firma.
    autor: foto.autor_tipo === 'INSPECTOR' ? `${foto.autor} (inspector)` : null,
    eliminable: puedeEliminarFoto(foto),
  }));

  return (
    <div>
      {puedeSubir && (
        <PhotoDropzone
          onDrop={handleDrop}
          loading={subiendo}
          helperText="JPG, PNG, WEBP, MP4, MOV o WEBM — hasta 50MB cada uno"
        />
      )}

      {!puedeSubir && items.length === 0 && (
        <Text c="dimmed" size="sm">
          Este reclamo no tiene fotos ni videos.
        </Text>
      )}

      <PhotoGrid
        items={items}
        onRemove={(fotoId) => setFotoAEliminar(items.find((item) => item.id === fotoId))}
        onSelect={setMediaAmpliada}
        removingId={eliminandoId}
      />

      <Modal
        opened={fotoAEliminar !== null}
        onClose={() => setFotoAEliminar(null)}
        title="Quitar foto"
        centered
      >
        <Text size="sm">
          ¿Quitar {fotoAEliminar?.alt}? Se borra del reclamo y no se puede deshacer.
        </Text>
        <Group justify="flex-end" mt="md">
          <Button variant="default" onClick={() => setFotoAEliminar(null)}>
            Cancelar
          </Button>
          <Button color="red" onClick={() => handleEliminar(fotoAEliminar.id)}>
            Quitar
          </Button>
        </Group>
      </Modal>

      <Modal
        opened={mediaAmpliada !== null}
        onClose={() => setMediaAmpliada(null)}
        title={
          mediaAmpliada?.autor
            ? `${mediaAmpliada.alt} — subida por ${mediaAmpliada.autor}`
            : mediaAmpliada?.alt
        }
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
