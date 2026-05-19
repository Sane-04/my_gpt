FROM node:24-alpine AS builder

WORKDIR /app

COPY package.json package-lock.json ./
RUN npm ci

COPY . .

ARG VITE_APP_ENV=production
ARG VITE_PUBLIC_API_BASE_URL=
ENV VITE_APP_ENV=$VITE_APP_ENV
ENV VITE_PUBLIC_API_BASE_URL=$VITE_PUBLIC_API_BASE_URL

RUN npm run build

CMD ["sh", "-c", "rm -rf /frontend-dist/* && cp -r /app/dist/. /frontend-dist/"]
