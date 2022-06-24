db:
	docker compose up -d
	@docker exec mongo /scripts/rs-init.sh

close:
	docker compose down

test:
	docker-compose down
	docker-compose up -d
	@docker exec mongo /scripts/rs-init.sh
	poetry run pytest --path tests/test_autotable_metadata_for_sql.py
	poetry run pytest --path tests/test_cli_generate_model_command.py
	poetry run pytest --path tests/test_crud_repository.py
	poetry run pytest --path tests/test_error_handling_at_repo_level.py
	poetry run pytest --path tests/test_for_pikachu_event_dispatcher.py
	poetry run pytest --path tests/test_igloo_container.py
	poetry run pytest --path tests/test_message_queue_system.py
	poetry run pytest --path tests/test_models_query_dsl.py
	poetry run pytest --path tests/test_models_serializatio_and_deserialization.py
	poetry run pytest --path tests/test_mongo_driver.py
	poetry run pytest --path tests/test_multi_repo_implementation.py
	poetry run pytest --path tests/test_parsing.py
	poetry run pytest --path tests/test_pg_driver.py
	poetry run pytest --path tests/test_pg_driver_against_db.py
	poetry run pytest --path tests/test_redis_eevents_handlers.py
	poetry run pytest --path tests/test_repository_agains_db.py
	poetry run pytest --path tests/test_sql_orm.py
	poetry run pytest --path tests/test_transactional_functions.py
	poetry run pytest --path tests/test_unit_of_work_with_mongo.py
	poetry run pytest --path tests/test_unit_of_work_with_pg.py
