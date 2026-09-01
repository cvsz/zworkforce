docker stop zrouter
docker rm zrouter
docker build -t zrouter .
docker run -d --name zrouter -p 20128:20128 --env-file .env -v zrouter-data:/app/data zrouter