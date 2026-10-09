# InvestiLens frontend image (Phase 5d). Production build served by nginx — this is the
# self-host / Render-static path; the primary target is Vercel (static build of `npm run build`),
# see docs/deployment notes + render.yaml. The docker-compose dev `frontend` service does NOT use
# this image; it runs `npm run dev` for hot reload.
FROM node:24-slim AS build
WORKDIR /app
COPY package.json package-lock.json ./
RUN npm ci
COPY . ./
# VITE_API_BASE_URL is baked at build time (the SPA calls the API cross-origin in prod).
ARG VITE_API_BASE_URL=/api/v1
ENV VITE_API_BASE_URL=$VITE_API_BASE_URL
RUN npm run build

FROM nginx:1.27-alpine AS runtime
COPY --from=build /app/dist /usr/share/nginx/html
COPY nginx.conf /etc/nginx/conf.d/default.conf
EXPOSE 80
