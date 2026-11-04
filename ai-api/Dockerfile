FROM node:22-slim
WORKDIR /app
COPY package*.json ./
RUN npm ci --omit=dev
COPY . .
ENV HOST=0.0.0.0 PORT=3000 NODE_ENV=production
USER node
EXPOSE 3000
CMD ["node", "index.js"]
