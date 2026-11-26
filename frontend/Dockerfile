FROM node:18-alpine as builder

WORKDIR /app

COPY package.json ./
RUN npm install

COPY . .
RUN NODE_OPTIONS=--max-old-space-size=1024 npm run build

FROM node:18-alpine

WORKDIR /app

RUN npm install -g serve

COPY --from=builder /app/dist ./dist
COPY start.sh write-runtime-config.cjs ./
RUN chmod +x /app/start.sh

EXPOSE 3000

CMD ["./start.sh"]
