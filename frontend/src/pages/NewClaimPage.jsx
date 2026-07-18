import { Container } from '@mantine/core';

import { SchoolClaimForm } from '../components/forms/SchoolClaimForm';

export function NewClaimPage() {
  return (
    <Container size="sm" py="xl">
      <SchoolClaimForm />
    </Container>
  );
}
