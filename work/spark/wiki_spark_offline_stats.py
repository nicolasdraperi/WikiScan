# -*- coding: utf-8 -*-
from pyspark.sql import SparkSession
from pyspark.sql.functions import col, count

# ======================
# CONFIG
# ======================
HDFS_BASE = "hdfs://namenode:9000/wikiscan/events"
OUTPUT_PATH = "hdfs://namenode:9000/wikiscan/offline_stats"

EVENT_TYPES = [
    "recentchange",
    "page-create",
    "page-delete"
]

WIKI = "*" 

# ======================
# SPARK
# ======================
spark = SparkSession.builder \
    .appName("WikiScan-Offline-Stats") \
    .getOrCreate()

spark.sparkContext.setLogLevel("WARN")

# ======================
# LOAD DATA
# ======================
for EVENT_TYPE in EVENT_TYPES:
    print("Processing:", EVENT_TYPE)

    input_path = "{}/event_source={}".format(HDFS_BASE, EVENT_TYPE)

    df = spark.read.parquet(input_path)

    # Sécurité si jamais il n’y a rien
    if df.rdd.isEmpty():
        print("No data for", EVENT_TYPE)
        continue

    # ===== AGGREGATIONS =====
    by_country = df.groupBy("country_code").count()
    by_wiki = df.groupBy("wiki").count()

    # ===== WRITE OFFLINE STATS =====
    by_country.coalesce(1).write.mode("overwrite").json(
        "{}/{}/by_country".format(OUTPUT_PATH, EVENT_TYPE)
    )

    by_wiki.coalesce(1).write.mode("overwrite").json(
        "{}/{}/by_wiki".format(OUTPUT_PATH, EVENT_TYPE)
    )



spark.stop()
