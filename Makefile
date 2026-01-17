# Makefile

.PHONY: help build run dev stop clean logs

help:
	@echo "Twitch Stream Extractor - Comandos disponibles:"
	@echo "  build    - Construye la imagen Docker"
	@echo "  run      - Ejecuta en modo producción (Gunicorn)"
	@echo "  dev      - Inicia en modo desarrollo (Flask + recarga)"
	@echo "  stop     - Detiene contenedores"
	@echo "  clean    - Elimina contenedores e imágenes"
	@echo "  logs     - Muestra logs del contenedor"

build:
	docker build -t twitch-extractor .

run: build
	docker run -d --name twitch-app -p 5000:5000 twitch-extractor

dev:
	docker-compose up --build

stop:
	docker-compose down

clean:
	docker-compose down -v
	docker rmi twitch-extractor 2>/dev/null || true
	docker rm -f twitch-app 2>/dev/null || true

logs:
	docker logs -f twitch-app 2>/dev/null || docker-compose logs -f