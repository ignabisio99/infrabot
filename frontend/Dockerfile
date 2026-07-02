FROM node:24-alpine

# Instalar pnpm globalmente
RUN corepack enable \
 && corepack prepare pnpm@10.13.1 --activate

WORKDIR /app

# Copiar archivos de configuración para instalar dependencias
COPY package.json pnpm-lock.yaml* ./
RUN pnpm install

# Copiar el resto de los archivos
COPY . .

# Exponer el puerto estándar de React
EXPOSE 3000

# Ejecutar la aplicación en modo desarrollo con pnpm/vite
CMD ["pnpm", "dev", "--host", "0.0.0.0"]
