# Dev container for the Vite dev server. Source is bind-mounted in by docker-compose.yml;
# node_modules lives in a named volume so container-installed (Linux) binaries never collide
# with anything installed on the host.
FROM node:20-alpine

WORKDIR /app

EXPOSE 5173

CMD ["sh", "-c", "npm install && npm run dev"]
