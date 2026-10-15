import { ActionIcon, Image, SimpleGrid, UnstyledButton } from '@mantine/core';
import { IconPlayerPlay, IconTrash } from '@tabler/icons-react';

function isVideo(item) {
  return item.tipo === 'VIDEO' || /\.(mp4|mov|webm|3gp)$/i.test(item.src);
}

function MediaThumbnail({ item, onClick }) {
  if (isVideo(item)) {
    return (
      <UnstyledButton onClick={onClick} h="100%" w="100%" style={{ position: 'relative' }}>
        <video
          src={item.src}
          muted
          preload="metadata"
          style={{
            width: '100%',
            height: '100%',
            objectFit: 'cover',
            borderRadius: 'var(--mantine-radius-md)',
          }}
        />
        <div
          style={{
            position: 'absolute',
            top: '50%',
            left: '50%',
            transform: 'translate(-50%, -50%)',
            background: 'rgba(0,0,0,0.6)',
            borderRadius: '50%',
            width: 36,
            height: 36,
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'center',
          }}
        >
          <IconPlayerPlay size={20} color="white" />
        </div>
      </UnstyledButton>
    );
  }

  if (onClick) {
    return (
      <UnstyledButton onClick={onClick} h="100%" w="100%">
        <Image src={item.src} alt={item.alt} radius="md" h="100%" w="100%" fit="cover" />
      </UnstyledButton>
    );
  }

  return <Image src={item.src} alt={item.alt} radius="md" h="100%" w="100%" fit="cover" />;
}

// Grilla de miniaturas con botón de borrar. `onSelect` es opcional (click para ampliar)
// y `removingId` también (id del ítem que se está borrando, para mostrar loading).
// Un ítem con `eliminable: false` no muestra el botón aunque haya `onRemove`.
export function PhotoGrid({ items, onRemove, onSelect, removingId }) {
  if (items.length === 0) return null;

  return (
    <SimpleGrid cols={{ base: 2, xs: 3, sm: 4 }} spacing="sm" mt="md">
      {items.map((item) => (
        <div key={item.id} style={{ position: 'relative', aspectRatio: '1 / 1' }}>
          <MediaThumbnail item={item} onClick={onSelect ? () => onSelect(item) : undefined} />
          {onRemove && item.eliminable !== false && (
            <ActionIcon
              variant="filled"
              color="red"
              size="sm"
              radius="xl"
              loading={removingId === item.id}
              onClick={(event) => {
                event.stopPropagation();
                onRemove(item.id);
              }}
              aria-label="Quitar archivo"
              style={{ position: 'absolute', top: 4, right: 4 }}
            >
              <IconTrash size={14} />
            </ActionIcon>
          )}
        </div>
      ))}
    </SimpleGrid>
  );
}
