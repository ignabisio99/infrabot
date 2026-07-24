import { IconX } from '@tabler/icons-react';
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
