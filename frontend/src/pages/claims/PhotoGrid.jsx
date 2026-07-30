import { ActionIcon, Image, SimpleGrid, UnstyledButton } from '@mantine/core';
import { IconTrash } from '@tabler/icons-react';

// Grilla de miniaturas con botón de borrar. `onSelect` es opcional (click para ampliar)
// y `removingId` también (id del ítem que se está borrando, para mostrar loading).
export function PhotoGrid({ items, onRemove, onSelect, removingId }) {
  if (items.length === 0) return null;

  return (
    <SimpleGrid cols={4} spacing="sm" mt="md">
      {items.map((item) => (
        <div key={item.id} style={{ position: 'relative', aspectRatio: '1 / 1' }}>
          {onSelect ? (
            <UnstyledButton onClick={() => onSelect(item)} h="100%" w="100%">
              <Image src={item.src} alt={item.alt} radius="md" h="100%" w="100%" fit="cover" />
            </UnstyledButton>
          ) : (
            <Image src={item.src} alt={item.alt} radius="md" h="100%" w="100%" fit="cover" />
          )}
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
            aria-label="Quitar foto"
            style={{ position: 'absolute', top: 4, right: 4 }}
          >
            <IconTrash size={14} />
          </ActionIcon>
        </div>
      ))}
    </SimpleGrid>
  );
}
