# WikiScan - Live Wikipedia Activity Map

Dashboard temps réel affichant l'activité Wikipedia mondiale sur une carte interactive.

![WikiScan Screenshot](https://img.shields.io/badge/Status-Live-brightgreen)
![Docker](https://img.shields.io/badge/Docker-Required-blue)
![Node.js](https://img.shields.io/badge/Node.js-18+-green)

---

## 📊 Architecture

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                              WIKISCAN ARCHITECTURE                          │
└─────────────────────────────────────────────────────────────────────────────┘

                    ┌──────────────────────────────┐
                    │   Wikimedia EventStreams     │
                    │   (SSE - Server Sent Events) │
                    │   stream.wikimedia.org       │
                    └──────────────┬───────────────┘
                                   │
                                   ▼
┌──────────────────────────────────────────────────────────────────────────────┐
│                           INGESTION LAYER                                    │
│  ┌────────────────────────────────────────────────────────────────────────┐  │
│  │                      Producer Python                                   │  │
│  │                      wiki_producer.py                                  │  │
│  │  • Lit le flux SSE en temps réel                                       │  │
│  │  • Enrichit les données (delta_bytes, country_code, language...)       │  │
│  │  • Publie sur Kafka topic "wiki-raw"                                   │  │
│  └────────────────────────────────────────────────────────────────────────┘  │
└──────────────────────────────────────────────────────────────────────────────┘
                                   │
                                   ▼
                         ┌─────────────────┐
                         │     KAFKA       │
                         │   topic:        │
                         │   wiki-raw      │
                         └────────┬────────┘
                                  │
                    ┌─────────────┴─────────────┐
                    │                           │
                    ▼                           ▼
┌───────────────────────────────┐  ┌───────────────────────────────┐
│      PERSISTENCE LAYER        │  │        INSIGHT LAYER          │
│  ┌─────────────────────────┐  │  │  ┌─────────────────────────┐  │
│  │    Spark Streaming      │  │  │  │    Node.js Server       │  │
│  │    wiki_spark_stream.py │  │  │  │    server.js            │  │
│  │                         │  │  │  │                         │  │
│  │  • Lit depuis Kafka     │  │  │  │  • Consomme Kafka       │  │
│  │  • Transforme les data  │  │  │  │  • WebSocket broadcast  │  │
│  │  • Écrit en Parquet     │  │  │  │  • Sert le frontend     │  │
│  └───────────┬─────────────┘  │  │  └───────────┬─────────────┘  │
│              │                │  │              │                │
│              ▼                │  │              ▼                │
│  ┌─────────────────────────┐  │  │  ┌─────────────────────────┐  │
│  │         HDFS            │  │  │  │    Frontend Leaflet     │  │
│  │   Format: Parquet       │  │  │  │    main.js              │  │
│  │   Partitions:           │  │  │  │                         │  │
│  │   wiki / event_date     │  │  │  │  • Carte interactive    │  │
│  └─────────────────────────┘  │  │  │  • Filtres Bot/Humain   │  │
│                               │  │  │  • Stats temps réel     │  │
└───────────────────────────────┘  │  └─────────────────────────┘  │
                                   └───────────────────────────────┘
```

---

## 🛠️ Stack Technique

| Composant | Technologie | Rôle |
|-----------|-------------|------|
| Message Broker | Apache Kafka | File d'attente des événements |
| Streaming | Spark Structured Streaming | ETL vers HDFS |
| Stockage | Hadoop HDFS (Parquet) | Persistance des données |
| Backend | Node.js + Express + WebSocket | API temps réel |
| Frontend | Leaflet.js | Carte interactive |
| Container | Docker Compose | Orchestration |

---

## 📁 Structure du Projet

```
WikiScan/
├── docker-compose.yml          # Infrastructure Docker
├── hadoop.env                  # Configuration Hadoop
├── README.md                   # Ce fichier
│
├── frontend/                   # Application Frontend
│   ├── server.js               # Serveur Node.js + WebSocket + Kafka
│   ├── package.json            # Dépendances Node.js
│   ├── public/
│   │   ├── index.html          # Page principale
│   │   ├── main.js             # Logique carte Leaflet
│   │   └── style.css           # Styles
│   └── data/
│       └── countries.geo.json  # GeoJSON des pays
│
└── work/                       # Backend Python
    ├── requirements.txt        # Dépendances Python
    ├── producer/
    │   └── wiki_producer.py    # Producer Kafka (WikiMedia → Kafka)
    └── spark/
        └── wiki_spark_stream.py # Spark Streaming (Kafka → HDFS)
```

---

## 🚀 Installation & Lancement

### Prérequis

- [Docker Desktop](https://www.docker.com/products/docker-desktop/) (avec Docker Compose)
- [Node.js](https://nodejs.org/) v18+
- 8 Go RAM minimum recommandé

### Étape 1 : Cloner le projet

```bash
git clone <url-du-repo>
cd WikiScan
```

### Étape 2 : Lancer l'infrastructure Docker

```bash
docker-compose up -d
```

Vérifier que tout tourne :
```bash
docker ps
```

Services lancés :
| Service | Port | URL |
|---------|------|-----|
| HDFS NameNode | 9870 | http://localhost:9870 |
| Spark Master | 8080 | http://localhost:8080 |
| Kafka | 29092 | localhost:29092 |
| Jupyter | 8888 | http://localhost:8888 |

### Étape 3 : Installer les dépendances Python

```bash
docker exec pyspark_notebook pip install kafka-python-ng requests
```

### Étape 4 : Lancer le Producer Kafka

```bash
docker exec pyspark_notebook python /home/jovyan/work/producer/wiki_producer.py
```

Le Producer va :
- Se connecter à WikiMedia EventStreams
- Enrichir les événements
- Publier sur le topic Kafka `wiki-raw`

### Étape 5 : Installer et lancer le Frontend

```bash
cd frontend
npm install
npm start
```

### Étape 6 : Ouvrir le dashboard

Ouvrir dans le navigateur : **http://localhost:3000**

---

## 📊 Lancer Spark Streaming (Optionnel - Stockage HDFS)

Pour sauvegarder les données dans HDFS :

```bash
docker exec wikiscan-spark-master-1 /spark/bin/spark-submit \
    --packages org.apache.spark:spark-sql-kafka-0-10_2.12:3.0.1 \
    /home/jovyan/work/spark/wiki_spark_stream.py
```

Les données seront stockées dans :
```
hdfs://namenode:9000/wikiscan/events/
├── wiki=frwiki/
│   └── event_date=2026-01-14/
├── wiki=enwiki/
│   └── event_date=2026-01-14/
└── ...
```

---

## 🔧 Configuration

### Variables d'environnement

| Variable | Défaut | Description |
|----------|--------|-------------|
| `KAFKA_BROKER` | `localhost:29092` | Adresse du broker Kafka |
| `PORT` | `3000` | Port du serveur frontend |

### Fichiers de configuration

- `hadoop.env` : Configuration du cluster Hadoop
- `docker-compose.yml` : Services Docker

---

## 📈 Données Enrichies

Le Producer enrichit chaque événement Wikipedia avec :

| Champ | Type | Description |
|-------|------|-------------|
| `delta_bytes` | Integer | Différence de taille (new - old) |
| `is_major_edit` | Boolean | `true` si \|delta\| > 500 bytes |
| `language` | String | Code langue (fr, en, de...) |
| `country_code` | String | Code pays ISO (FR, GB, DE...) |
| `hour_of_day` | Integer | Heure de l'événement (0-23) |
| `date` | String | Date YYYY-MM-DD |
| `processed_at` | String | Timestamp de traitement |

---

## 🗺️ Mapping Wiki → Pays

| Wiki | Pays | Code |
|------|------|------|
| frwiki | France | FR |
| enwiki | Royaume-Uni | GB |
| dewiki | Allemagne | DE |
| eswiki | Espagne | ES |
| itwiki | Italie | IT |
| jawiki | Japon | JP |
| zhwiki | Chine | CN |
| ruwiki | Russie | RU |
| ... | ... | ... |

---

## 🛑 Arrêt

### Arrêter le frontend
```bash
Ctrl+C
```

### Arrêter Docker
```bash
docker-compose down
```

### Arrêter et supprimer les volumes (reset complet)
```bash
docker-compose down -v
```

---

## 🐛 Dépannage

### Kafka ne démarre pas
```bash
docker-compose restart kafka
```

### Erreur "checkpoint" Spark
```bash
docker exec namenode hdfs dfs -rm -r /wikiscan/checkpoints
```

### Vérifier les topics Kafka
```bash
docker exec kafka kafka-topics --list --bootstrap-server localhost:9092
```

### Vérifier les messages dans Kafka
```bash
docker exec kafka kafka-run-class kafka.tools.GetOffsetShell \
    --broker-list localhost:9092 --topic wiki-raw
```

---

## 👥 Équipe

- **Backend** : Producer Kafka, Spark Streaming, HDFS
- **Frontend** : Dashboard Leaflet, WebSocket

---

## 📝 Licence

Projet éducatif IPSSI - Big Data DataLake
