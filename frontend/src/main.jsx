import { StrictMode } from 'react';
import { createRoot } from 'react-dom/client';
import { MantineProvider } from '@mantine/core';
import '@mantine/core/styles.css';
import '@mantine/charts/styles.css';
import { DatesProvider } from '@mantine/dates';
import '@mantine/dates/styles.css';
import '@mantine/dropzone/styles.css';
import { Notifications } from '@mantine/notifications';
import '@mantine/notifications/styles.css';
import 'react-big-calendar/lib/css/react-big-calendar.css';
import { GoogleOAuthProvider } from '@react-oauth/google';
import dayjs from 'dayjs';
import 'dayjs/locale/es';
import { BrowserRouter } from 'react-router';

import App from './App.jsx';

// react-big-calendar lee el locale global de dayjs (localeData ignora el argumento),
// así que sin esto la semana arranca en domingo.
dayjs.locale('es');

const GOOGLE_CLIENT_ID = import.meta.env.VITE_GOOGLE_CLIENT_ID || '';

createRoot(document.getElementById('root')).render(
  <StrictMode>
    <GoogleOAuthProvider clientId={GOOGLE_CLIENT_ID}>
      <MantineProvider>
        <Notifications position="bottom-left" />
        <DatesProvider settings={{ locale: 'es' }}>
          <BrowserRouter>
            <App />
          </BrowserRouter>
        </DatesProvider>
      </MantineProvider>
    </GoogleOAuthProvider>
  </StrictMode>,
);
