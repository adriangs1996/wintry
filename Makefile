db:
	docker compose up -d
	@docker exec mongo /scripts/rs-init.sh

close:
	docker compose down