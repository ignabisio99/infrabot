import { useRef, useState } from 'react';

const MIME_CANDIDATOS = [
  'audio/webm;codecs=opus',
  'audio/webm',
  'audio/ogg;codecs=opus',
  'audio/mp4',
];

function mimePreferido() {
  if (typeof MediaRecorder === 'undefined') return '';
  return MIME_CANDIDATOS.find((tipo) => MediaRecorder.isTypeSupported(tipo)) || '';
}

function extensionDe(mime) {
  if (mime.includes('ogg')) return 'ogg';
  if (mime.includes('mp4')) return 'm4a';
  return 'webm';
}

export function useGrabarAudio() {
  const [grabando, setGrabando] = useState(false);
  const recorderRef = useRef(null);
  const chunksRef = useRef([]);
  const streamRef = useRef(null);

  const soltarMic = () => {
    streamRef.current?.getTracks().forEach((track) => track.stop());
    streamRef.current = null;
  };

  const empezar = async () => {
    if (grabando) return;
    if (!navigator.mediaDevices?.getUserMedia || typeof MediaRecorder === 'undefined') {
      throw new Error('Este navegador no puede grabar audio. Usá Chrome o Edge.');
    }
    const stream = await navigator.mediaDevices.getUserMedia({ audio: true });
    streamRef.current = stream;
    chunksRef.current = [];
    const mime = mimePreferido();
    const recorder = mime
      ? new MediaRecorder(stream, { mimeType: mime })
      : new MediaRecorder(stream);
    recorderRef.current = recorder;
    recorder.ondataavailable = (evento) => {
      if (evento.data.size > 0) chunksRef.current.push(evento.data);
    };
    recorder.start();
    setGrabando(true);
  };

  const detener = () =>
    new Promise((resolve, reject) => {
      const recorder = recorderRef.current;
      if (!recorder || recorder.state === 'inactive') {
        setGrabando(false);
        soltarMic();
        resolve(null);
        return;
      }
      recorder.onstop = () => {
        soltarMic();
        setGrabando(false);
        const tipo = recorder.mimeType || 'audio/webm';
        const blob = new Blob(chunksRef.current, { type: tipo.split(';')[0] });
        chunksRef.current = [];
        if (blob.size < 100) {
          resolve(null);
          return;
        }
        resolve(
          new File([blob], `nota-voz.${extensionDe(tipo)}`, { type: blob.type }),
        );
      };
      recorder.onerror = (evento) => {
        soltarMic();
        setGrabando(false);
        reject(evento.error || new Error('No se pudo grabar el audio.'));
      };
      recorder.stop();
    });

  return { grabando, empezar, detener };
}
