# -*- coding: utf-8 -*-
"""
==============================================
WikiScan - Spark Structured Streaming
==============================================
Lit les événements depuis Kafka, les transforme
et les stocke dans HDFS au format Parquet.

Supporte :
- recentchange
- page-create
- page-delete

Partitionnement :
event_source / wiki / event_date
==============================================
"""

from pyspark.sql import SparkSession
from pyspark.sql.functions import col, from_json
from pyspark.sql.types import (
    StructType, StructField,
    StringType, LongType,
    BooleanType, IntegerType
)

# ======================
# CONFIGURATION
# ======================
KAFKA_BOOTSTRAP_SERVERS = "kafka:9092"
KAFKA_TOPIC = "wiki-raw"

HDFS_OUTPUT_PATH = "hdfs://namenode:9000/wikiscan/events"
CHECKPOINT_PATH = "hdfs://namenode:9000/wikiscan/checkpoints"

# ======================
# SCHEMA DES DONNEES
# ======================
wiki_event_schema = StructType([

    # Identifiants
    StructField("id", LongType(), True),
    StructField("type", StringType(), True),
    StructField("event_source", StringType(), True),

    # Page
    StructField("namespace", IntegerType(), True),
    StructField("title", StringType(), True),
    StructField("comment", StringType(), True),

    # Temps
    StructField("timestamp", LongType(), True),
    StructField("date", StringType(), True),
    StructField("hour_of_day", IntegerType(), True),

    # Utilisateur
    StructField("user", StringType(), True),
    StructField("bot", BooleanType(), True),
    StructField("minor", BooleanType(), True),
    StructField("patrolled", BooleanType(), True),

    # Wiki / Geo
    StructField("wiki", StringType(), True),
    StructField("language", StringType(), True),
    StructField("country_code", StringType(), True),

    # Métriques
    StructField("delta_bytes", LongType(), True),
    StructField("is_major_edit", BooleanType(), True),

    # Meta
    StructField("server_name", StringType(), True),
    StructField("processed_at", StringType(), True),
])

# ======================
# SPARK SESSION
# ======================
def create_spark_session():
    spark = (
        SparkSession.builder
        .appName("WikiScan-Streaming")
        .config("spark.sql.streaming.checkpointLocation", CHECKPOINT_PATH)
        .config("spark.sql.parquet.compression.codec", "snappy")
        .getOrCreate()
    )
    spark.sparkContext.setLogLevel("WARN")
    return spark

# ======================
# MAIN
# ======================
def main():
    print("=" * 60)
    print("[START] WikiScan - Spark Structured Streaming")
    print("=" * 60)

    spark = create_spark_session()
    print("[OK] Session Spark prête")

    # ======================
    # LECTURE KAFKA
    # ======================
    kafka_df = (
        spark.readStream
        .format("kafka")
        .option("kafka.bootstrap.servers", KAFKA_BOOTSTRAP_SERVERS)
        .option("subscribe", KAFKA_TOPIC)
        .option("startingOffsets", "earliest")
        .option("failOnDataLoss", "false")
        .load()
    )

    print("[OK] Connecté à Kafka")

    # ======================
    # PARSING JSON
    # ======================
    parsed_df = (
        kafka_df
        .selectExpr(
            "CAST(key AS STRING) AS kafka_key",
            "CAST(value AS STRING) AS json_value"
        )
        .select(
            col("kafka_key"),
            from_json(col("json_value"), wiki_event_schema).alias("data")
        )
        .select("kafka_key", "data.*")
    )

    # ======================
    # TRANSFORMATIONS
    # ======================
    transformed_df = parsed_df.select(
        col("id").alias("event_id"),
        col("event_source"),
        col("wiki"),
        col("type").alias("event_type"),
        col("namespace"),
        col("title"),
        col("comment"),
        col("user").alias("username"),
        col("bot").alias("is_bot"),
        col("timestamp").alias("event_timestamp"),
        col("date").alias("event_date"),
        col("hour_of_day"),
        col("delta_bytes"),
        col("is_major_edit"),
        col("language"),
        col("country_code"),
        col("minor").alias("is_minor"),
        col("patrolled").alias("is_patrolled"),
        col("server_name"),
        col("processed_at"),
    )

    # ======================
    # FILTRAGE
    # ======================
    filtered_df = (
        transformed_df
        .filter(col("wiki").isNotNull())
        .filter(col("event_source").isNotNull())
    )

    print("[INFO] Écriture HDFS :", HDFS_OUTPUT_PATH)
    print("[INFO] Partitionnement : event_source / wiki / event_date")
    print("=" * 60)
    print("[STREAMING] En cours...")
    print("=" * 60)

    # ======================
    # ECRITURE HDFS
    # ======================
    query = (
        filtered_df.writeStream
        .format("parquet")
        .outputMode("append")
        .partitionBy("event_source", "wiki", "event_date")
        .option("path", HDFS_OUTPUT_PATH)
        .option("checkpointLocation", CHECKPOINT_PATH)
        .trigger(processingTime="10 seconds")
        .start()
    )

    try:
        query.awaitTermination()
    except KeyboardInterrupt:
        print("\n[STOP] Arrêt demandé")
        query.stop()
    finally:
        spark.stop()
        print("[END] Streaming arrêté proprement")

# ======================
# ENTRYPOINT
# ======================
if __name__ == "__main__":
    main()
