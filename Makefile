# Makefile

.PHONY: help build run dev stop clean logs ps icons

help:
	@echo "Twitch Stream Extractor - Comandos disponibles:"
	@echo "  build    - Construye la imagen Docker"
	@echo "  run      - Ejecuta en modo producción (Gunicorn)"
	@echo "  dev      - Inicia en modo desarrollo (Flask + recarga)"
	@echo "  stop     - Detiene contenedores"
	@echo "  clean    - Elimina contenedores e imágenes"
	@echo "  logs     - Muestra logs del contenedor"
	@echo "  ps       - Estado de los contenedores y si la app responde"
	@echo "  icons    - Regenera PNG/ICO/manifest desde assets/*.svg"
	@echo ""
	@echo "Para cambiar la marca: edita assets/icon.svg y ejecuta 'make icons'."

build:
	docker build -t twitch-extractor .

run: build
	-docker rm -f twitch-app
	docker run -d --name twitch-app -p 5000:5000 \
		$(if $(wildcard .env),--env-file .env,) \
		twitch-extractor

dev:
	docker-compose up --build

# make dev levanta twitch-extractor (docker compose) y make run levanta
# twitch-app (docker run). 'docker compose down' solo afecta al primero, así
# que parar solo uno dejaba el otro en marcha: se parar los dos por nombre.
stop:
	@if ! command -v docker >/dev/null 2>&1; then \
		echo "docker no está instalado o no está en el PATH."; \
	else \
		seen=0; stopped=0; \
		for c in twitch-app twitch-extractor; do \
			if ! docker container inspect "$$c" >/dev/null 2>&1; then continue; fi; \
			seen=1; \
			if [ "$$(docker inspect -f '{{.State.Running}}' "$$c" 2>/dev/null)" = "true" ]; then \
				docker stop "$$c" >/dev/null && echo "  parado: $$c"; \
				stopped=1; \
			else \
				echo "  $$c ya estaba parado"; \
			fi; \
		done; \
		if [ "$$seen" -eq 0 ]; then \
			echo "No hay contenedores. Arranca con 'make run' o 'make dev'."; \
		fi; \
	fi

# Elimina contenedores e imagen. Los dos nombres, por el mismo motivo que
# en 'stop'. Primero los contenedores: 'docker rmi' falla si la imagen la
# sigue usando un contenedor parado.
clean:
	@if command -v docker >/dev/null 2>&1; then \
		for c in twitch-app twitch-extractor; do \
			docker rm -f "$$c" >/dev/null 2>&1 && echo "  eliminado: $$c"; \
		done; \
		docker rmi twitch-extractor >/dev/null 2>&1 || true; \
	fi
	@echo "Limpio."

logs:
	docker logs -f twitch-app 2>/dev/null || docker-compose logs -f

# Estado de los contenedores. Hay dos nombres según cómo se arrancó:
# twitch-app (make run) y twitch-extractor (make dev).
ps:
	@if ! command -v docker >/dev/null 2>&1; then \
		echo "docker no está instalado o no está en el PATH."; \
	elif ! docker info >/dev/null 2>&1; then \
		echo "el daemon de docker no responde."; \
	else \
		found=0; \
		for c in twitch-app twitch-extractor; do \
			if docker container inspect "$$c" >/dev/null 2>&1; then \
				found=1; \
				case "$$c" in \
					twitch-app) src="make run" ;; \
					*)         src="make dev" ;; \
				esac; \
				state=$$(docker inspect -f '{{.State.Status}}' "$$c"); \
				ports=$$(docker port "$$c" 2>/dev/null | tr '\n' ' '); \
				echo "$$c  [$$src]"; \
				echo "    estado  : $$state"; \
				if [ -n "$$ports" ]; then echo "    puertos : $$ports"; fi; \
				hostport=$$(docker port "$$c" 2>/dev/null | head -1 | awk -F: '{print $$NF}'); \
				if [ -n "$$hostport" ] && command -v curl >/dev/null 2>&1; then \
					code=$$(curl -s -o /dev/null -w '%{http_code}' -m 5 "http://localhost:$$hostport/" 2>/dev/null); \
					[ -z "$$code" ] && code=000; \
					case "$$code" in \
						2*|3*) echo "    http    : OK ($$code) en http://localhost:$$hostport/" ;; \
						000)   echo "    http    : sin respuesta en http://localhost:$$hostport/" ;; \
						*)     echo "    http    : devuelve $$code en http://localhost:$$hostport/" ;; \
					esac; \
				fi; \
			fi; \
		done; \
		if [ "$$found" -eq 0 ]; then \
			echo "No hay contenedores. Arranca con 'make run' o 'make dev'."; \
		fi; \
	fi

# Regenera todos los iconos e imagen sociales desde assets/*.svg.
# Los PNG resultantes se commitean en static/: la imagen Docker no lleva
# rsvg-convert ni fuentes, así que el render se hace en el host.
icons:
	./tools/generate-assets.sh