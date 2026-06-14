# Build the React app, then serve the static bundle with nginx.
FROM node:22-alpine AS build
WORKDIR /app
COPY package.json ./
RUN npm install
COPY . .
# API/WS default to localhost:8091 (the ws-gateway, reached from the browser on the host).
# Override at build time with --build-arg VITE_API_URL=... / VITE_WS_URL=... if needed.
ARG VITE_API_URL
ARG VITE_WS_URL
RUN npm run build

FROM nginx:alpine
COPY --from=build /app/dist /usr/share/nginx/html
COPY nginx.conf /etc/nginx/conf.d/default.conf
EXPOSE 80
