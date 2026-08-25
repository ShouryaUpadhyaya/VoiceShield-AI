FROM node:22-slim
WORKDIR /app
COPY package.json package-lock.json ./
RUN npm ci --omit=dev
COPY dist/ ./dist/
COPY .env.example .env
EXPOSE 8010
CMD ["node", "dist/server.js"]
