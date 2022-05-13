from datetime import date, datetime


from enum import Enum

__mappings_builtins__ = (int, str, Enum, float, bool, bytes, date, datetime, dict, set)
__sequences_like__ = (dict, list, set)
__RepositoryType__ = "__winter_repository_type__"
__winter_in_session_flag__ = "__winter_in_session_flag__"
__SQL_ENABLED_FLAG__ = "__sqlalchemy_managed_entity__"
__WINTER_MAPPED_CLASS__ = "__winter_mapped_class__"
__winter_track_target__ = "__winter_track_target__"
__winter_tracker__ = "__winter_tracker__"
__winter_modified_entity_state__ = "__winter_modified_entity_state__"
__winter_old_setattr__ = "__winter_old_setattr__"
__winter_repo_old_init__ = "__winter_repo_old_init__"
__winter_manage_objects__ = "__winter_manage_objects__"
__winter_session_key__ = "__winter_session_key__"
__winter_backend_identifier_key__ = "__winter_backend_identifier_key__"
__winter_backend_for_repository__ = "__winter_backend_for_repository__"
__winter_repository_for_model__ = "__winter_repository_for_model__"
__winter_repository_is_using_sqlalchemy__ = "__winter_repository_is_using_sqlalchemy__"
__winter_model_collection_name__ = "__winter_model_collection_name__"
__winter_transporter_name__ = "__winter_transporter_name__"
__winter_microservice_event__ = "__winter_microservice_event__"

NO_SQL = "NO_SQL"
SQL = "SQL"
