FROM node:18-alpine as builder

WORKDIR /app

COPY package.json package-lock.json ./
RUN npm ci

COPY . .
RUN npm run build

FROM node:18-alpine

WORKDIR /app

RUN npm install -g serve

RUN chmod +x start.sh

COPY --from=builder /app/dist ./dist
COPY start.sh .

EXPOSE 3000

CMD ["./start.sh"]
