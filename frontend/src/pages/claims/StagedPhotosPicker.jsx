import { useEffect, useMemo } from 'react';

import { PhotoDropzone } from './PhotoDropzone';
import { PhotoGrid } from './PhotoGrid';

// Selector de fotos "en espera": no las sube todavía, solo las guarda en memoria
// (con una preview local) hasta que el que las use decida crear el reclamo.
export function StagedPhotosPicker({ archivos, onChange }) {
  const previewUrls = useMemo(() => {
    const map = {};
    for (const item of archivos) map[item.id] = URL.createObjectURL(item.file);
    return map;
  }, [archivos]);

  useEffect(() => {
    return () => {
      for (const url of Object.values(previewUrls)) URL.revokeObjectURL(url);
    };
  }, [previewUrls]);

  const handleDrop = (nuevosArchivos) => {
    const nuevos = nuevosArchivos.map((file) => ({ id: crypto.randomUUID(), file }));
    onChange([...archivos, ...nuevos]);
  };

  const handleQuitar = (id) => {
    onChange(archivos.filter((item) => item.id !== id));
  };

  const items = archivos.map((item) => ({
    id: item.id,
    src: previewUrls[item.id],
    alt: item.file.name,
  }));

  return (
    <div>
      <PhotoDropzone
        onDrop={handleDrop}
        helperText="JPG, PNG o WEBP, hasta 10 MB cada una. Se suben al enviar el reclamo."
      />

      <PhotoGrid items={items} onRemove={handleQuitar} />
    </div>
  );
}
