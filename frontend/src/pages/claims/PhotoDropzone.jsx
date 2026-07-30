import { Text } from '@mantine/core';
import { Dropzone, IMAGE_MIME_TYPE } from '@mantine/dropzone';
import { IconPhotoUp, IconUpload, IconX } from '@tabler/icons-react';

export function PhotoDropzone({ onDrop, loading = false, helperText }) {
  return (
    <Dropzone onDrop={onDrop} loading={loading} accept={IMAGE_MIME_TYPE} maxSize={5 * 1024 ** 2}>
      <div style={{ display: 'flex', alignItems: 'center', gap: 12, minHeight: 80 }}>
        <Dropzone.Accept>
          <IconUpload size={32} color="var(--mantine-color-blue-6)" />
        </Dropzone.Accept>
        <Dropzone.Reject>
          <IconX size={32} color="var(--mantine-color-red-6)" />
        </Dropzone.Reject>
        <Dropzone.Idle>
          <IconPhotoUp size={32} color="var(--mantine-color-dimmed)" />
        </Dropzone.Idle>
        <div>
          <Text size="sm">Arrastrá fotos acá o hacé clic para seleccionarlas</Text>
          <Text size="xs" c="dimmed">
            {helperText}
          </Text>
        </div>
      </div>
    </Dropzone>
  );
}
