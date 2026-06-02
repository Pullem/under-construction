import logging
import mariadb
import time
from contextlib import contextmanager

logger = logging.getLogger(__name__)

class DB:
    def __init__(self, host="localhost", port=3306, user="vfa_user", password="vfa_password", database="vfa_db"):
        self._host = host
        self._port = port
        self._user = user
        self._password = password
        self._database = database

        # Try to create a connection pool for the requested database. If the
        # database does not exist, create it and retry.
        try:
            logger.debug("Creating ConnectionPool for database '%s'@%s:%s", database, host, port)
            self.pool = mariadb.ConnectionPool(
                pool_name="vfa_pool",
                pool_size=5,
                host=host, port=port, user=user, password=password, database=database
            )
        except mariadb.Error as e:
            logger.warning("ConnectionPool creation failed: %s", e)
            # If database is missing, create it and retry
            if getattr(e, 'errno', None) in (1049,):  # Unknown database
                logger.info("Database '%s' not found, attempting to create it", database)
                conn = mariadb.connect(host=host, port=port, user=user, password=password)
                try:
                    cur = conn.cursor()
                    cur.execute(f"CREATE DATABASE IF NOT EXISTS `{database}`")
                    conn.commit()
                    logger.info("Database '%s' created (or already existed)", database)
                finally:
                    conn.close()
                # retry creating the pool
                logger.debug("Retrying ConnectionPool creation for database '%s'", database)
                self.pool = mariadb.ConnectionPool(
                    pool_name="vfa_pool",
                    pool_size=5,
                    host=host, port=port, user=user, password=password, database=database
                )
            else:
                logger.exception("Failed to create ConnectionPool and database is not missing: %s", e)
                raise

        # ensure required tables exist
        logger.debug("Ensuring required tables exist in database '%s'", database)
        self._ensure_tables()

    @contextmanager
    def connection(self):
        # Try to get a connection from the pool with retries. When many
        # worker threads run concurrently the pool can be exhausted and the
        # connector will raise an error. Instead of failing immediately we
        # retry for a short time to allow connections to be returned.
        retries = 30
        delay = 0.1
        conn = None
        for attempt in range(retries):
            try:
                conn = self.pool.get_connection()
                break
            except Exception as e:
                # Log and retry briefly
                logger.debug("No connection available (attempt %d/%d): %s", attempt + 1, retries, e)
                time.sleep(delay)
        if conn is None:
            # final attempt without swallowing the exception
            conn = self.pool.get_connection()

        try:
            yield conn
        finally:
            try:
                conn.close()
            except Exception:
                logger.exception("Failed to close DB connection")

    def _ensure_tables(self):
        """Create required tables if they do not exist."""
        media_sql = """
        CREATE TABLE IF NOT EXISTS mediafiles (
            id INT AUTO_INCREMENT PRIMARY KEY,
            file_path TEXT,
            file_name VARCHAR(255),
            file_size BIGINT,
            hash VARCHAR(128),
            created_at DATETIME,
            last_modified DATETIME
        ) ENGINE=InnoDB
        """

        param_sql = """
        CREATE TABLE IF NOT EXISTS mi_parameter (
            id INT AUTO_INCREMENT PRIMARY KEY,
            mediafile_id INT,
            category VARCHAR(255),
            parameter VARCHAR(255),
            value TEXT,
            FOREIGN KEY (mediafile_id) REFERENCES mediafiles(id) ON DELETE CASCADE
        ) ENGINE=InnoDB
        """

        with self.connection() as conn:
            cur = conn.cursor()
            logger.debug("Creating table 'mediafiles' if not exists")
            cur.execute(media_sql)
            logger.debug("Creating table 'mi_parameter' if not exists")
            cur.execute(param_sql)
            conn.commit()
            logger.info("Ensured tables 'mediafiles' and 'mi_parameter' exist")
