FROM node:18

WORKDIR /app

COPY package.json ./
RUN npm install

COPY . .

RUN npm run build

# Serve static files using simple Node server (or Nginx)
RUN npm install -g serve
CMD ["serve", "-s", "public", "-l", "3000"]
