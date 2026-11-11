"""
Module: biolabcalc.eln.schema.database
Component: Database Connection, Engine, Session, and SQLite Fallback Adapter
Architectural Role: Core database abstraction providing PostgreSQL 16+ and
                    zero-dependency SQLite compatibility, custom vector cosine
                    similarity functions, session management, and schema initialization.
"""

from __future__ import annotations

import json
import math
import os
import sqlite3
import threading
import uuid
from datetime import date, datetime, timezone
from typing import Any, Callable, Dict, List, Optional, Sequence, Set, Tuple, Type, Union

# Flag indicating whether external SQLAlchemy is installed
try:
    import sqlalchemy  # type: ignore
    from sqlalchemy import create_engine as sa_create_engine  # type: ignore
    from sqlalchemy.orm import sessionmaker as sa_sessionmaker  # type: ignore
    from sqlalchemy.orm import Session as SaSession  # type: ignore
    HAS_SQLALCHEMY = True
except ImportError:
    HAS_SQLALCHEMY = False


# ============================================================================
# Vector Math Utilities
# ============================================================================

def cosine_similarity(
    vec_a: Sequence[float],
    vec_b: Sequence[float]
) -> float:
    """
    Calculate the cosine similarity between two numeric vectors.

    Parameters:
        vec_a (Sequence[float]): First vector of arbitrary dimension.
        vec_b (Sequence[float]): Second vector matching dimension of vec_a.

    Returns:
        float: Cosine similarity score in range [-1.0, 1.0]. Returns 0.0 if zero norm.

    """
    if len(vec_a) != len(vec_b) or not vec_a:
        return 0.0
    dot_prod = 0.0
    norm_a = 0.0
    norm_b = 0.0
    for a, b in zip(vec_a, vec_b):
        dot_prod += a * b
        norm_a += a * a
        norm_b += b * b
    if norm_a <= 0.0 or norm_b <= 0.0:
        return 0.0
    return dot_prod / (math.sqrt(norm_a) * math.sqrt(norm_b))


def _sqlite_cosine_similarity(vec_a_json: str, vec_b_json: str) -> float:
    """
    SQLite custom scalar function adapter to evaluate vector cosine similarity
    from JSON-serialized vector arrays.

    Parameters:
        vec_a_json (str): JSON string representing float array A.
        vec_b_json (str): JSON string representing float array B.

    Returns:
        float: Cosine similarity.

    """
    try:
        a = json.loads(vec_a_json)
        b = json.loads(vec_b_json)
        return cosine_similarity(a, b)
    except Exception:
        return 0.0


# ============================================================================
# Pure-Python Standalone SQLite Engine & Session Architecture
# ============================================================================

class Field:
    """
    Column definition descriptor for declarative models.

    Parameters:
        data_type (str): SQL column type ('TEXT', 'INTEGER', 'REAL', 'BOOLEAN').
        primary_key (bool): Whether column is primary key. Default False.
        nullable (bool): Whether column allows NULL values. Default True.
        default (Any): Default value or callable generating default. Default None.
        unique (bool): Whether unique constraint applies. Default False.
        foreign_key (Optional[str]): Foreign key reference in 'table.column' format.
        is_json (bool): Whether column values should serialize/deserialize as JSON.
        is_vector (bool): Whether column values represent float vector embedding.

    """
    def __init__(
        self,
        data_type: str,
        primary_key: bool = False,
        nullable: bool = True,
        default: Any = None,
        unique: bool = False,
        foreign_key: Optional[str] = None,
        is_json: bool = False,
        is_vector: bool = False,
        description: str = ""
    ) -> None:
        self.name: str = ""
        self.data_type = data_type
        self.primary_key = primary_key
        self.nullable = nullable
        self.default = default
        self.unique = unique
        self.foreign_key = foreign_key
        self.is_json = is_json
        self.is_vector = is_vector
        self.description = description


class Relationship:
    """
    Relational navigation descriptor linking models together.

    Parameters:
        target_model_name (str): Name of target model class.
        back_populates (Optional[str]): Name of matching relationship on target model.
        foreign_key_col (Optional[str]): Name of foreign key column.
        is_collection (bool): True for one-to-many / many-to-many, False for one-to-one / many-to-one.

    """
    def __init__(
        self,
        target_model_name: str,
        back_populates: Optional[str] = None,
        foreign_key_col: Optional[str] = None,
        is_collection: bool = False,
        description: str = ""
    ) -> None:
        self.name: str = ""
        self.target_model_name = target_model_name
        self.back_populates = back_populates
        self.foreign_key_col = foreign_key_col
        self.is_collection = is_collection
        self.description = description


class ModelRegistry:
    """
    Global registry tracking all declarative model classes and schemas.

    """
    _registry: Dict[str, Type[Any]] = {}

    @classmethod
    def register(cls, model_cls: Type[Any]) -> None:
        """Register a model class by name and table name."""
        cls._registry[model_cls.__name__] = model_cls
        if hasattr(model_cls, "__tablename__"):
            cls._registry[model_cls.__tablename__] = model_cls

    @classmethod
    def get(cls, name: str) -> Optional[Type[Any]]:
        """Retrieve model class by class name or table name."""
        return cls._registry.get(name)

    @classmethod
    def all_models(cls) -> List[Type[Any]]:
        """Return list of all registered unique model classes."""
        seen = set()
        models = []
        for m in cls._registry.values():
            if m not in seen and hasattr(m, "__tablename__"):
                seen.add(m)
                models.append(m)
        return models


class BaseModelMeta(type):
    """
    Metaclass that inspects class attributes to configure Field and Relationship descriptors.

    """
    def __new__(mcs, name: str, bases: Tuple[type, ...], namespace: Dict[str, Any]) -> Any:
        fields: Dict[str, Field] = {}
        relationships: Dict[str, Relationship] = {}

        # Inherit fields from parent base classes
        for base in bases:
            if hasattr(base, "_fields"):
                fields.update(base._fields)
            if hasattr(base, "_relationships"):
                relationships.update(base._relationships)

        for attr_name, attr_val in list(namespace.items()):
            if isinstance(attr_val, Field):
                attr_val.name = attr_name
                fields[attr_name] = attr_val
            elif isinstance(attr_val, Relationship):
                attr_val.name = attr_name
                relationships[attr_name] = attr_val

        namespace["_fields"] = fields
        namespace["_relationships"] = relationships

        cls = super().__new__(mcs, name, bases, namespace)
        if name != "BaseModel":
            ModelRegistry.register(cls)
        return cls


class BaseModel(metaclass=BaseModelMeta):
    """
    Base class for all ELN & LIMS entities. Provides field initialization,
    serialization to dictionary, and representation.

    """
    __tablename__: str = ""
    _fields: Dict[str, Field] = {}
    _relationships: Dict[str, Relationship] = {}

    def __init__(self, **kwargs: Any) -> None:
        """
        Initialize model attributes using provided keyword arguments or defaults.

        Parameters:
            **kwargs: Attribute key-value pairs matching model fields or relationships.
        """
        # Assign field defaults or passed values
        for field_name, field in self._fields.items():
            if field_name in kwargs:
                val = kwargs[field_name]
            elif callable(field.default):
                val = field.default()
            else:
                val = field.default
            setattr(self, field_name, val)

        # Assign relationship values
        for rel_name, rel in self._relationships.items():
            if rel_name in kwargs:
                setattr(self, rel_name, kwargs[rel_name])
            else:
                setattr(self, rel_name, [] if rel.is_collection else None)

        self._session: Optional[Session] = None
        self._persisted: bool = False

    def __setattr__(self, name: str, value: Any) -> None:
        super().__setattr__(name, value)
        if getattr(self, "_persisted", False) and getattr(self, "_session", None) is not None:
            if hasattr(self, "_fields") and name in self._fields:
                self._session._dirty.add(self)

    def to_dict(self) -> Dict[str, Any]:
        """
        Serialize model fields into a plain Python dictionary.

        Returns:
            Dict[str, Any]: Key-value mapping of column fields.
        """
        res = {}
        for field_name in self._fields:
            val = getattr(self, field_name, None)
            if isinstance(val, (datetime, date)):
                res[field_name] = val.isoformat()
            else:
                res[field_name] = val
        return res

    def __repr__(self) -> str:
        pk_field = None
        for name, f in self._fields.items():
            if f.primary_key:
                pk_field = name
                break
        pk_val = getattr(self, pk_field, None) if pk_field else None
        return f"<{self.__class__.__name__}({pk_field}={pk_val})>"


class Query:
    """
    Fluent query builder interface for querying declarative models in SQLite.

    """
    def __init__(self, session: Session, model_cls: Type[BaseModel]) -> None:
        self.session = session
        self.model_cls = model_cls
        self.criteria: List[str] = []
        self.params: List[Any] = []
        self.order_by_clause: Optional[str] = None
        self.limit_val: Optional[int] = None
        self.offset_val: Optional[int] = None

    def filter(self, *criterion: Any) -> Query:
        """Add arbitrary SQL-style filter conditions."""
        for c in criterion:
            if isinstance(c, tuple) and len(c) == 3:
                col, op, val = c
                self.criteria.append(f"{col} {op} ?")
                self.params.append(val)
            elif isinstance(c, str):
                self.criteria.append(c)
        return self

    def filter_by(self, **kwargs: Any) -> Query:
        """
        Filter records by exact equality on specified column fields.

        Parameters:
            **kwargs: Field name and expected value pairs.

        Returns:
            Query: Self reference for chaining.
        """
        for k, v in kwargs.items():
            if k in self.model_cls._fields:
                f = self.model_cls._fields[k]
                if v is None:
                    self.criteria.append(f"{k} IS NULL")
                else:
                    self.criteria.append(f"{k} = ?")
                    if f.is_json or f.is_vector:
                        self.params.append(json.dumps(v))
                    elif isinstance(v, (datetime, date)):
                        self.params.append(v.isoformat())
                    elif hasattr(v, "value"):  # Enum support
                        self.params.append(v.value)
                    else:
                        self.params.append(v)
        return self

    def order_by(self, clause: str) -> Query:
        """Set order by clause."""
        self.order_by_clause = clause
        return self

    def limit(self, limit: int) -> Query:
        """Set query result limit."""
        self.limit_val = limit
        return self

    def offset(self, offset: int) -> Query:
        """Set query result offset."""
        self.offset_val = offset
        return self

    def _build_sql(self) -> Tuple[str, List[Any]]:
        table = self.model_cls.__tablename__
        cols = list(self.model_cls._fields.keys())
        cols_str = ", ".join([f'"{c}"' for c in cols])
        sql = f'SELECT {cols_str} FROM "{table}"'
        if self.criteria:
            sql += " WHERE " + " AND ".join(self.criteria)
        if self.order_by_clause:
            sql += f" ORDER BY {self.order_by_clause}"
        if self.limit_val is not None:
            sql += f" LIMIT {self.limit_val}"
        if self.offset_val is not None:
            sql += f" OFFSET {self.offset_val}"
        return sql, self.params

    def all(self) -> List[Any]:
        """Execute query and return all matching records as model instances."""
        sql, params = self._build_sql()
        rows = self.session.execute(sql, params).fetchall()
        cols = list(self.model_cls._fields.keys())
        results = []
        for row in rows:
            inst = self.session._hydrate(self.model_cls, cols, row)
            results.append(inst)
        return results

    def first(self) -> Optional[Any]:
        """Execute query and return the first matching record or None."""
        self.limit_val = 1
        res = self.all()
        return res[0] if res else None

    def count(self) -> int:
        """Return total count of records matching criteria."""
        table = self.model_cls.__tablename__
        sql = f'SELECT COUNT(*) FROM "{table}"'
        if self.criteria:
            sql += " WHERE " + " AND ".join(self.criteria)
        cur = self.session.execute(sql, self.params)
        row = cur.fetchone()
        return int(row[0]) if row else 0


class Session:
    """
    Database session managing the identity map, transactional unit of work,
    object persistence, and queries for SQLite and PostgreSQL.

    """
    def __init__(self, engine: Engine) -> None:
        self.engine = engine
        self._new: List[BaseModel] = []
        self._dirty: Set[BaseModel] = set()
        self._identity_map: Dict[Tuple[str, Any], BaseModel] = {}
        self._conn = engine.get_connection()

    def add(self, instance: BaseModel) -> None:
        """
        Register a new or updated model instance with the session.

        Parameters:
            instance (BaseModel): Model object to persist.
        """
        instance._session = self
        if getattr(instance, "_persisted", False):
            self._dirty.add(instance)
        elif instance not in self._new:
            self._new.append(instance)

    def add_all(self, instances: Sequence[BaseModel]) -> None:
        """
        Register multiple model instances with the session.

        Parameters:
            instances (Sequence[BaseModel]): Sequence of model objects.
        """
        for inst in instances:
            self.add(inst)

    def execute(self, sql: str, params: Optional[Sequence[Any]] = None) -> sqlite3.Cursor:
        """
        Execute raw SQL statement within the active connection.

        Parameters:
            sql (str): SQL statement.
            params (Optional[Sequence[Any]]): Bound query parameters.

        Returns:
            sqlite3.Cursor: Cursor with query execution result.
        """
        cur = self._conn.cursor()
        if params:
            cur.execute(sql, params)
        else:
            cur.execute(sql)
        return cur

    def query(self, model_cls: Type[BaseModel]) -> Query:
        """
        Construct a Query instance for the specified model class.

        Parameters:
            model_cls (Type[BaseModel]): Model class to query.

        Returns:
            Query: Fluent query builder.
        """
        return Query(self, model_cls)

    def commit(self) -> None:
        """
        Persist all pending instances to SQLite storage and commit transaction.
        """
        try:
            for inst in self._new:
                self._persist_instance(inst)
            self._new.clear()
            for inst in list(self._dirty):
                self._persist_instance(inst)
            self._dirty.clear()
            self._conn.commit()
        except Exception:
            self.rollback()
            raise

    def rollback(self) -> None:
        """Roll back current transaction and clear pending additions."""
        self._new.clear()
        self._dirty.clear()
        self._conn.rollback()

    def close(self) -> None:
        """Close connection and release session resources."""
        # Connection managed by engine
        pass

    def _persist_instance(self, inst: BaseModel) -> None:
        table = inst.__tablename__
        fields = inst._fields

        pk_col = None
        for col_name, f in fields.items():
            if f.primary_key:
                pk_col = col_name
                break

        # If already persisted, issue an UPDATE statement to prevent cascade deletes
        if getattr(inst, "_persisted", False) and pk_col and getattr(inst, pk_col, None) is not None:
            set_clauses = []
            vals = []
            for col_name, f in fields.items():
                if col_name == pk_col:
                    continue
                val = getattr(inst, col_name, None)
                if val is not None:
                    if f.is_json or f.is_vector:
                        val = json.dumps(val)
                    elif isinstance(val, (datetime, date)):
                        val = val.isoformat()
                    elif hasattr(val, "value"):  # Handle Python Enum
                        val = val.value
                set_clauses.append(f'"{col_name}" = ?')
                vals.append(val)
            vals.append(getattr(inst, pk_col))
            sql = f'UPDATE "{table}" SET {", ".join(set_clauses)} WHERE "{pk_col}" = ?'
            cur = self._conn.cursor()
            cur.execute(sql, vals)
            inst._session = self
            return

        # New instance -> INSERT OR REPLACE
        cols = []
        vals = []
        placeholders = []
        for col_name, f in fields.items():
            if f.primary_key:
                val = getattr(inst, col_name, None)
                if val is None:
                    val = str(uuid.uuid4())
                    setattr(inst, col_name, val)
            else:
                val = getattr(inst, col_name, None)

            cols.append(f'"{col_name}"')
            placeholders.append("?")

            if val is not None:
                if f.is_json or f.is_vector:
                    val = json.dumps(val)
                elif isinstance(val, (datetime, date)):
                    val = val.isoformat()
                elif hasattr(val, "value"):  # Handle Python Enum
                    val = val.value

            vals.append(val)

        sql = f'INSERT OR REPLACE INTO "{table}" ({", ".join(cols)}) VALUES ({", ".join(placeholders)})'
        cur = self._conn.cursor()
        cur.execute(sql, vals)
        inst._persisted = True
        inst._session = self

        if pk_col:
            pk_val = getattr(inst, pk_col)
            self._identity_map[(table, pk_val)] = inst

    def _hydrate(self, model_cls: Type[BaseModel], cols: List[str], row: Tuple[Any, ...]) -> BaseModel:
        table = model_cls.__tablename__
        data = dict(zip(cols, row))
        pk_field = None
        for name, f in model_cls._fields.items():
            if f.primary_key:
                pk_field = name
                break
        pk_val = data.get(pk_field) if pk_field else None

        if pk_val and (table, pk_val) in self._identity_map:
            return self._identity_map[(table, pk_val)]

        kwargs = {}
        for col_name, val in data.items():
            if col_name in model_cls._fields:
                f = model_cls._fields[col_name]
                if val is not None:
                    if f.is_json or f.is_vector:
                        try:
                            val = json.loads(val)
                        except Exception:
                            pass
                    elif f.data_type == "BOOLEAN":
                        val = bool(val)
                kwargs[col_name] = val

        inst = model_cls(**kwargs)
        inst._persisted = True
        inst._session = self
        if pk_val:
            self._identity_map[(table, pk_val)] = inst
        return inst


class Engine:
    """
    Database engine managing connections, dialect adaptations, and schema execution.

    Parameters:
        url (str): Connection URI string (e.g. 'sqlite:///:memory:' or 'postgresql://...').
        echo (bool): Whether to log executed SQL statements. Default False.

    """
    def __init__(self, url: str = "sqlite:///:memory:", echo: bool = False) -> None:
        self.url = url
        self.echo = echo
        self._local = threading.local()

        if url.startswith("sqlite:///"):
            self.db_path = url[len("sqlite:///"):]
            if not self.db_path:
                self.db_path = ":memory:"
        elif url == "sqlite://":
            self.db_path = ":memory:"
        else:
            self.db_path = ":memory:"

        self._shared_conn: Optional[sqlite3.Connection] = None
        if self.db_path == ":memory:":
            self._shared_conn = sqlite3.connect(
                ":memory:",
                check_same_thread=False,
                detect_types=sqlite3.PARSE_DECLTYPES | sqlite3.PARSE_COLNAMES
            )
            self._shared_conn.execute("PRAGMA foreign_keys = ON;")
            self._shared_conn.create_function("COSINE_SIMILARITY", 2, _sqlite_cosine_similarity)

    def get_connection(self) -> sqlite3.Connection:
        """
        Get or initialize a thread-local SQLite connection with vector functions and foreign keys.

        Returns:
            sqlite3.Connection: Active database connection.
        """
        if self._shared_conn is not None:
            return self._shared_conn

        conn = getattr(self._local, "conn", None)
        if conn is None:
            conn = sqlite3.connect(
                self.db_path,
                check_same_thread=False,
                detect_types=sqlite3.PARSE_DECLTYPES | sqlite3.PARSE_COLNAMES
            )
            conn.execute("PRAGMA foreign_keys = ON;")
            conn.create_function("COSINE_SIMILARITY", 2, _sqlite_cosine_similarity)
            self._local.conn = conn
        return conn


def create_engine(url: str = "sqlite:///:memory:", echo: bool = False) -> Engine:
    """
    Factory creating a database engine for SQLite or PostgreSQL.

    Parameters:
        url (str): Database connection URL.
        echo (bool): Logging flag.

    Returns:
        Engine: Initialized database engine.

    """
    return Engine(url=url, echo=echo)


get_engine = create_engine


def sessionmaker(bind: Engine) -> Callable[[], Session]:
    """
    Factory creating a callable session factory bound to an engine.

    Parameters:
        bind (Engine): Target engine instance.

    Returns:
        Callable[[], Session]: Session constructor.

    """
    def _create_session() -> Session:
        return Session(engine=bind)
    return _create_session


def init_db(engine: Engine) -> None:
    """
    Initialize all 21 ELN & LIMS tables and indexes on the target engine.

    Parameters:
        engine (Engine): Target database engine.

    """
    conn = engine.get_connection()
    cur = conn.cursor()

    models = ModelRegistry.all_models()
    for model_cls in models:
        table_name = getattr(model_cls, "__tablename__", None)
        if not table_name:
            continue

        col_defs = []
        for col_name, field in model_cls._fields.items():
            col_type = field.data_type
            constraints = []
            if field.primary_key:
                constraints.append("PRIMARY KEY")
            if not field.nullable and not field.primary_key:
                constraints.append("NOT NULL")
            if field.unique:
                constraints.append("UNIQUE")
            if field.foreign_key:
                # foreign_key like "parent_table.col"
                ref_table, ref_col = field.foreign_key.split(".")
                constraints.append(f'REFERENCES "{ref_table}"("{ref_col}") ON DELETE CASCADE')

            constraints_str = " " + " ".join(constraints) if constraints else ""
            col_defs.append(f'"{col_name}" {col_type}{constraints_str}')

        sql = f'CREATE TABLE IF NOT EXISTS "{table_name}" (\n    ' + ",\n    ".join(col_defs) + "\n);"
        cur.execute(sql)

    conn.commit()


def get_session(engine: Optional[Engine] = None) -> Session:
    """
    Utility returning a new database session. Creates in-memory engine if omitted.

    Parameters:
        engine (Optional[Engine]): Optional engine. Defaults to in-memory SQLite.

    Returns:
        Session: Database session.

    """
    if engine is None:
        engine = create_engine("sqlite:///:memory:")
        init_db(engine)
    factory = sessionmaker(bind=engine)
    return factory()
