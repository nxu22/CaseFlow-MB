# Alpine keeps the dev image small. Day 3 production will use multi-stage build.
FROM node:22-alpine

WORKDIR /app

# Copy package files first for Docker layer caching.
COPY package*.json ./
RUN npm install

# Then copy source.
COPY . .

EXPOSE 3000

# Development server with hot reload.
CMD ["npm", "run", "dev"]
