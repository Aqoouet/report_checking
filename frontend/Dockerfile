ARG NODE_IMAGE=node:20-slim
ARG NGINX_IMAGE=nginx:alpine
FROM ${NODE_IMAGE} AS builder

WORKDIR /app
COPY package*.json ./
RUN npm ci
COPY . .
RUN npm run build

FROM ${NGINX_IMAGE}
COPY --from=builder /app/dist /usr/share/nginx/html
COPY nginx.conf /etc/nginx/conf.d/default.conf
EXPOSE 80
