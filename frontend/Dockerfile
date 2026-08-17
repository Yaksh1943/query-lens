# Dev-only image: runs the Vite dev server with hot reload.
# (A separate production build step will be added when deployment
# is actually set up — see docs/ROADMAP.md.)
FROM node:20-alpine

WORKDIR /app

COPY package.json .
RUN npm install

COPY . .

EXPOSE 5173

CMD ["npm", "run", "dev", "--", "--host", "0.0.0.0"]
