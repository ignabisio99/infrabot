import { ActionIcon, Menu } from '@mantine/core';
import { IconDots, IconEdit, IconTrash } from '@tabler/icons-react';

// `extraItems` permite sumar acciones propias de una entidad (ej. cambiar el estado
// de un reclamo) sin que este componente, que es compartido, las tenga que conocer.
export function RowActionsMenu({
  onEdit,
  onDelete,
  deleting,
  extraItems,
  editDisabled = false,
  deleteDisabled = false,
}) {
  return (
    <Menu position="bottom-end" withinPortal shadow="sm">
      <Menu.Target>
        <ActionIcon
          variant="subtle"
          size="sm"
          aria-label="Acciones"
          onClick={(event) => event.stopPropagation()}
        >
          <IconDots size={16} />
        </ActionIcon>
      </Menu.Target>
      <Menu.Dropdown onClick={(event) => event.stopPropagation()}>
        <Menu.Item leftSection={<IconEdit size={14} />} onClick={onEdit} disabled={editDisabled}>
          Editar
        </Menu.Item>
        {extraItems}
        <Menu.Item
          color="red"
          leftSection={<IconTrash size={14} />}
          onClick={onDelete}
          disabled={deleting || deleteDisabled}
        >
          {deleting ? 'Eliminando...' : 'Eliminar'}
        </Menu.Item>
      </Menu.Dropdown>
    </Menu>
  );
}
