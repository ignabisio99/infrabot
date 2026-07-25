import { IconCheck, IconX } from '@tabler/icons-react';
import { notifications } from '@mantine/notifications';

export function notifyError(message) {
  notifications.show({
    color: 'red',
    title: 'Error',
    message,
    withBorder: true,
    icon: <IconX size={18} />,
  });
}

export function notifySuccess(message) {
  notifications.show({
    color: 'green',
    title: 'Éxito',
    message,
    withBorder: true,
    icon: <IconCheck size={18} />,
  });
}
