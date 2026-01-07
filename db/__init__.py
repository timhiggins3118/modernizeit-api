"""
Database module for ModernizeIT API.

SQLite Tables:
- jobs: Job tracking
- aws_credentials: AWS credentials storage
- saved_flows: Saved workflow configurations

MongoDB Collections:
- code_analysis: Code analysis artifacts (raw JSON)
"""

from db.jobs import (
    JobRecord,
    init_db as init_jobs_table,
    save_job,
    get_job,
)

from db.aws_credentials import (
    AWSCredentials,
    init_aws_credentials_table,
    save_credentials,
    get_credentials,
    delete_credentials,
)

from db.accounts import (
    Account,
    init_accounts_table,
    save_account,
    get_account,
    get_all_accounts,
    delete_account,
    get_account_s3_config,
)

from db.flows import (
    SavedFlowRecord,
    init_db as init_flows_table,
    save_flow,
    get_flow,
    list_flows,
    delete_flow,
    update_flow_name,
)

from db.mongodb import (
    get_mongodb_client,
    get_database,
    close_mongodb,
    get_code_analysis_collection,
    store_code_analysis_artifact,
    get_code_analysis_artifacts,
)


def init_db() -> None:
    """Initialize all database tables (SQLite only - MongoDB is lazy-init)."""
    init_jobs_table()
    init_aws_credentials_table()
    init_accounts_table()
    init_flows_table()


__all__ = [
    # Jobs (SQLite)
    "JobRecord",
    "save_job",
    "get_job",
    # AWS Credentials (SQLite)
    "AWSCredentials",
    "save_credentials",
    "get_credentials",
    "delete_credentials",
    # Accounts (SQLite)
    "Account",
    "save_account",
    "get_account",
    "get_all_accounts",
    "delete_account",
    "get_account_s3_config",
    # Saved Flows (SQLite)
    "SavedFlowRecord",
    "save_flow",
    "get_flow",
    "list_flows",
    "delete_flow",
    "update_flow_name",
    # MongoDB
    "get_mongodb_client",
    "get_database",
    "close_mongodb",
    "get_code_analysis_collection",
    "store_code_analysis_artifact",
    "get_code_analysis_artifacts",
    # Init
    "init_db",
]
