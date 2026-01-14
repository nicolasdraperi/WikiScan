# -*- coding: utf-8 -*-
"""
==============================================
WikiScan - Spark Structured Streaming
==============================================
Lit les evenements depuis Kafka, les transforme et les stocke
dans HDFS au format Parquet, partitionne par wiki et date.

Usage (depuis le container spark-master):
    spark-submit --packages org.apache.spark:spark-sql-kafka-0-10_2.12:3.0.1 \
        /home/jovyan/work/spark/wiki_spark_stream.py

==============================================
"""

from pyspark.sql import SparkSession
from pyspark.sql.functions import (
    col, from_json, to_timestamp, hour, date_format,
    when, abs as spark_abs, lit
)
from pyspark.sql.types import (
    StructType, StructField, StringType, LongType, 
    BooleanType, IntegerType, MapType
)

# ======================
# CONFIGURATION
# ======================
KAFKA_BOOTSTRAP_SERVERS = "kafka:9092"
KAFKA_TOPIC = "wiki-raw"
HDFS_OUTPUT_PATH = "hdfs://namenode:9000/wikiscan/events"
CHECKPOINT_PATH = "hdfs://namenode:9000/wikiscan/checkpoints"

# ======================
# SCHEMA DES DONNEES KAFKA
# ======================
wiki_event_schema = StructType([
    # Donnees originales
    StructField("id", LongType(), True),
    StructField("type", StringType(), True),
    StructField("namespace", IntegerType(), True),
    StructField("title", StringType(), True),
    StructField("title_url", StringType(), True),
    StructField("comment", StringType(), True),
    StructField("timestamp", LongType(), True),
    StructField("user", StringType(), True),
    StructField("bot", BooleanType(), True),
    StructField("minor", BooleanType(), True),
    StructField("patrolled", BooleanType(), True),
    StructField("wiki", StringType(), True),
    StructField("server_name", StringType(), True),
    StructField("server_url", StringType(), True),
    
    # Donnees de longueur (nested)
    StructField("length", MapType(StringType(), LongType()), True),
    
    # Donnees de revision (nested)
    StructField("revision", MapType(StringType(), LongType()), True),
    
    # Enrichissements ajoutes par le Producer
    StructField("delta_bytes", LongType(), True),
    StructField("is_major_edit", BooleanType(), True),
    StructField("language", StringType(), True),
    StructField("country_code", StringType(), True),
    StructField("hour_of_day", IntegerType(), True),
    StructField("date", StringType(), True),
    StructField("processed_at", StringType(), True),
])


def create_spark_session():
    """Cree et configure la session Spark."""
    spark = SparkSession.builder \
        .appName("WikiScan-Streaming") \
        .config("spark.sql.streaming.checkpointLocation", CHECKPOINT_PATH) \
        .config("spark.sql.parquet.compression.codec", "snappy") \
        .getOrCreate()
    
    spark.sparkContext.setLogLevel("WARN")
    return spark


def main():
    print("=" * 60)
    print("[START] WikiScan - Spark Structured Streaming")
    print("=" * 60)
    
    # Creer la session Spark
    spark = create_spark_session()
    print("[OK] Session Spark creee")
    
    # Lire depuis Kafka
    print("[INFO] Connexion a Kafka: " + KAFKA_BOOTSTRAP_SERVERS)
    print("[INFO] Topic: " + KAFKA_TOPIC)
    
    kafka_df = spark.readStream \
        .format("kafka") \
        .option("kafka.bootstrap.servers", KAFKA_BOOTSTRAP_SERVERS) \
        .option("subscribe", KAFKA_TOPIC) \
        .option("startingOffsets", "earliest") \
        .option("failOnDataLoss", "false") \
        .load()
    
    print("[OK] Connecte a Kafka")
    
    # Parser le JSON depuis Kafka
    parsed_df = kafka_df \
        .selectExpr("CAST(key AS STRING) as kafka_key", "CAST(value AS STRING) as json_value") \
        .select(
            col("kafka_key"),
            from_json(col("json_value"), wiki_event_schema).alias("data")
        ) \
        .select("kafka_key", "data.*")
    
    # Selectionner et transformer les colonnes pertinentes
    transformed_df = parsed_df.select(
        # Identifiants
        col("id").alias("event_id"),
        col("wiki"),
        col("type").alias("event_type"),
        col("namespace"),
        
        # Contenu
        col("title"),
        col("comment"),
        
        # Utilisateur
        col("user").alias("username"),
        col("bot").alias("is_bot"),
        
        # Timing
        col("timestamp").alias("event_timestamp"),
        col("date").alias("event_date"),
        col("hour_of_day"),
        
        # Metriques
        col("delta_bytes"),
        col("is_major_edit"),
        
        # Geo
        col("language"),
        col("country_code"),
        
        # Meta
        col("minor").alias("is_minor"),
        col("patrolled").alias("is_patrolled"),
        col("server_name"),
        col("processed_at"),
    )
    
    # Filtrer les evenements valides (avec un wiki defini)
    filtered_df = transformed_df.filter(col("wiki").isNotNull())
    
    print("[INFO] Output HDFS: " + HDFS_OUTPUT_PATH)
    print("[INFO] Partitionnement: wiki / event_date")
    print("=" * 60)
    print("[STREAMING] En cours... (Ctrl+C pour arreter)")
    print("=" * 60)
    
    # Ecrire dans HDFS en Parquet, partitionne par wiki et date
    query = filtered_df.writeStream \
        .format("parquet") \
        .outputMode("append") \
        .partitionBy("wiki", "event_date") \
        .option("path", HDFS_OUTPUT_PATH) \
        .option("checkpointLocation", CHECKPOINT_PATH) \
        .trigger(processingTime="10 seconds") \
        .start()
    
    # Attendre la fin du streaming (ou Ctrl+C)
    try:
        query.awaitTermination()
    except KeyboardInterrupt:
        print("\n[STOP] Arret demande...")
        query.stop()
        print("[END] Streaming arrete proprement.")
    finally:
        spark.stop()


if __name__ == "__main__":
    main()
