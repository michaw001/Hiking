SERVER      := 192.168.1.87
SSH_USER    := michael
DEPLOY_PATH := ~/Docker_Images/hiking
SSH         := ssh $(SSH_USER)@$(SERVER)

REGISTRY    := 192.168.1.87:5000
IMAGE_NAME  := hiking
IMAGE_TAG   := latest
FULL_IMAGE  := $(REGISTRY)/$(IMAGE_NAME):$(IMAGE_TAG)

.DEFAULT_GOAL := help

.PHONY: help deploy build push up down restart logs ps clean-registry

help:
	@echo ""
	@echo "  deploy         - Bauen, pushen und auf Server neu starten"
	@echo "  build          - Docker-Image lokal bauen"
	@echo "  push           - Image in lokale Registry pushen"
	@echo "  up             - App auf Server starten"
	@echo "  down           - App auf Server stoppen"
	@echo "  restart        - App auf Server neu starten"
	@echo "  logs           - Live-Logs vom Server anzeigen"
	@echo "  ps             - Container-Status auf Server anzeigen"
	@echo "  clean-registry - Alte Images aus Registry löschen"
	@echo ""

deploy: build push
	@echo ">>> docker-compose.yml + .env.docker übertragen..."
	$(SSH) "mkdir -p $(DEPLOY_PATH)"
	rsync -az docker-compose.yml .env.docker $(SSH_USER)@$(SERVER):$(DEPLOY_PATH)/
	@echo ">>> App auf Server neu starten..."
	$(SSH) "cd $(DEPLOY_PATH) && docker compose pull && docker compose up -d"
	@echo ">>> Fertig. App läuft auf http://$(SERVER):8089"

build:
	@echo ">>> Image bauen: $(FULL_IMAGE)"
	docker build -t $(FULL_IMAGE) .

push:
	@echo ">>> Image in Registry pushen: $(FULL_IMAGE)"
	docker push $(FULL_IMAGE)

up:
	$(SSH) "cd $(DEPLOY_PATH) && docker compose up -d"

down:
	$(SSH) "cd $(DEPLOY_PATH) && docker compose down"

restart:
	$(SSH) "cd $(DEPLOY_PATH) && docker compose restart"

logs:
	$(SSH) "cd $(DEPLOY_PATH) && docker compose logs -f"

ps:
	$(SSH) "cd $(DEPLOY_PATH) && docker compose ps"

clean-registry:
	@echo ">>> Manifest-Digest aus Registry lesen..."
	@DIGEST=$$(curl -sI \
	    -H "Accept: application/vnd.docker.distribution.manifest.v2+json" \
	    http://$(REGISTRY)/v2/$(IMAGE_NAME)/manifests/$(IMAGE_TAG) \
	    | grep -i "docker-content-digest" | tr -d '\r' | awk '{print $$2}'); \
	if [ -z "$$DIGEST" ]; then \
	    echo "Kein Manifest gefunden."; \
	else \
	    echo "Lösche Manifest: $$DIGEST"; \
	    curl -s -X DELETE "http://$(REGISTRY)/v2/$(IMAGE_NAME)/manifests/$$DIGEST" && \
	    echo ">>> Garbage Collection starten..." && \
	    $(SSH) "docker exec registry registry garbage-collect \
	        /etc/docker/registry/config.yml --delete-untagged=true" && \
	    echo ">>> Registry bereinigt."; \
	fi
