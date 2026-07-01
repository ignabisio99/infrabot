FROM node:20-alpine

# Instalar pnpm globalmente
RUN npm install -g pnpm

WORKDIR /app

# Copiar archivos de configuración para instalar dependencias
COPY package.json ./
RUN pnpm install 

# Copiar el resto de los archivos
COPY . .

# Exponer el puerto estándar de React
EXPOSE 3000

# Ejecutar la aplicación en modo desarrollo con pnpm
CMD ["pnpm", "start", "--", "--host", "0.0.0.0"]
