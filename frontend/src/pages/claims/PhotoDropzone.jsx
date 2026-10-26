import { Text } from '@mantine/core';
import { Dropzone, IMAGE_MIME_TYPE } from '@mantine/dropzone';
import { IconPhotoUp, IconUpload, IconX } from '@tabler/icons-react';

const VIDEO_MIME_TYPES = ['video/mp4', 'video/quicktime', 'video/webm', 'video/3gpp'];
const ACCEPTED_MIME_TYPES = [...IMAGE_MIME_TYPE, ...VIDEO_MIME_TYPES];

export function PhotoDropzone({ onDrop, loading = false, helperText }) {
  return (
    <Dropzone
      onDrop={onDrop}
      loading={loading}
      accept={ACCEPTED_MIME_TYPES}
      // Mismo tope que el backend para los videos (core/storage.py); las fotos, 10 MB.
      maxSize={25 * 1024 ** 2}
    >
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
          <Text size="sm">Arrastrá fotos o videos acá, o hacé clic para seleccionarlos</Text>
          <Text size="xs" c="dimmed">
            {helperText}
          </Text>
        </div>
      </div>
    </Dropzone>
  );
}
