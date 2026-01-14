"""
==============================================
WikiScan - Producer Kafka
==============================================
Lit le flux SSE de Wikimedia EventStreams et publie sur Kafka.

Usage:
    python wiki_producer.py

Stream source: https://stream.wikimedia.org/v2/stream/recentchange
==============================================
"""

import json
import time
from datetime import datetime
from kafka import KafkaProducer
import requests

# ======================
# CONFIGURATION
# ======================
WIKIMEDIA_STREAM_URL = "https://stream.wikimedia.org/v2/stream/recentchange"
KAFKA_BOOTSTRAP_SERVERS = "kafka:9092"
KAFKA_TOPIC_RAW = "wiki-raw"

# Mapping wiki -> country code (ISO 3166-1 alpha-2)
WIKI_TO_COUNTRY = {
    "arwiki": "EG",      # Égypte (monde arabe)
    "arywiki": "MA",     # Maroc
    "cywiki": "GB",      # Pays de Galles
    "dewiki": "DE",      # Allemagne
    "elwiki": "GR",      # Grèce
    "enwiki": "GB",      # Anglophone (UK symbolique)
    "eswiki": "ES",      # Espagne
    "frwiki": "FR",      # France
    "hewiki": "IL",      # Israël
    "hiwiki": "IN",      # Inde (Hindi)
    "huwiki": "HU",      # Hongrie
    "idwiki": "ID",      # Indonésie
    "itwiki": "IT",      # Italie
    "jawiki": "JP",      # Japon
    "kowiki": "KR",      # Corée du Sud
    "ltwiki": "LT",      # Lituanie
    "nlwiki": "NL",      # Pays-Bas
    "plwiki": "PL",      # Pologne
    "ptwiki": "PT",      # Portugal
    "rowiki": "RO",      # Roumanie
    "ruwiki": "RU",      # Russie
    "svwiki": "SE",      # Suède
    "tawiki": "IN",      # Inde (Tamil)
    "thwiki": "TH",      # Thaïlande
    "trwiki": "TR",      # Turquie
    "ukwiki": "UA",      # Ukraine
    "urwiki": "PK",      # Pakistan
    "viwiki": "VN",      # Vietnam
    "zhwiki": "CN",      # Chine
}


def create_kafka_producer():
    """Crée et retourne un producer Kafka."""
    max_retries = 5
    for attempt in range(max_retries):
        try:
            producer = KafkaProducer(
                bootstrap_servers=KAFKA_BOOTSTRAP_SERVERS,
                value_serializer=lambda v: json.dumps(v, ensure_ascii=False).encode('utf-8'),
                key_serializer=lambda k: k.encode('utf-8') if k else None,
                acks='all',
                retries=3
            )
            print(f"✅ Connecté à Kafka ({KAFKA_BOOTSTRAP_SERVERS})")
            return producer
        except Exception as e:
            print(f"⚠️ Tentative {attempt + 1}/{max_retries} - Erreur connexion Kafka: {e}")
            time.sleep(5)
    
    raise Exception("❌ Impossible de se connecter à Kafka après plusieurs tentatives")


def enrich_event(event):
    """
    Enrichit un événement avec des données calculées.
    
    Ajouts:
    - delta_bytes: différence de taille (new - old)
    - language: code langue extrait du wiki
    - country_code: code pays ISO
    - hour_of_day: heure de l'événement
    - is_major_edit: si |delta| > 500 bytes
    - processed_at: timestamp de traitement
    """
    enriched = event.copy()
    
    # Delta bytes
    if "length" in event and event["length"]:
        old_len = event["length"].get("old", 0) or 0
        new_len = event["length"].get("new", 0) or 0
        enriched["delta_bytes"] = new_len - old_len
        enriched["is_major_edit"] = abs(enriched["delta_bytes"]) > 500
    else:
        enriched["delta_bytes"] = 0
        enriched["is_major_edit"] = False
    
    # Language & Country
    wiki = event.get("wiki", "")
    if wiki.endswith("wiki"):
        enriched["language"] = wiki.replace("wiki", "")
    else:
        enriched["language"] = wiki
    
    enriched["country_code"] = WIKI_TO_COUNTRY.get(wiki, None)
    
    # Heure du jour
    timestamp = event.get("timestamp", 0)
    if timestamp:
        dt = datetime.utcfromtimestamp(timestamp)
        enriched["hour_of_day"] = dt.hour
        enriched["date"] = dt.strftime("%Y-%m-%d")
    
    # Timestamp de traitement
    enriched["processed_at"] = datetime.utcnow().isoformat()
    
    return enriched


def stream_to_kafka(producer):
    """
    Lit le flux SSE Wikimedia et publie sur Kafka.
    """
    headers = {
        "Accept": "text/event-stream",
        "User-Agent": "WikiScan-Producer/1.0 (Educational Project)"
    }
    
    print(f"🌐 Connexion à {WIKIMEDIA_STREAM_URL}...")
    
    event_count = 0
    start_time = time.time()
    
    while True:
        try:
            with requests.get(WIKIMEDIA_STREAM_URL, headers=headers, stream=True, timeout=60) as response:
                response.raise_for_status()
                print("✅ Connecté au flux Wikimedia EventStreams")
                
                for line in response.iter_lines(decode_unicode=True):
                    if not line:
                        continue
                    
                    if line.startswith("data:"):
                        data_str = line[5:].strip()  # Enlève "data:" 
                        
                        try:
                            event = json.loads(data_str)
                            
                            # Enrichir l'événement
                            enriched_event = enrich_event(event)
                            
                            # Clé de partitionnement = wiki (ex: frwiki, enwiki)
                            key = enriched_event.get("wiki", "unknown")
                            
                            # Publier sur Kafka
                            producer.send(KAFKA_TOPIC_RAW, key=key, value=enriched_event)
                            
                            event_count += 1
                            
                            # Log toutes les 100 événements
                            if event_count % 100 == 0:
                                elapsed = time.time() - start_time
                                rate = event_count / elapsed
                                print(f"📊 {event_count} événements publiés ({rate:.1f}/sec) - Dernier: {enriched_event.get('wiki')} - {enriched_event.get('title', '')[:50]}")
                        
                        except json.JSONDecodeError:
                            pass  # Ignorer les lignes mal formées
                        except Exception as e:
                            print(f"⚠️ Erreur traitement événement: {e}")
        
        except requests.exceptions.RequestException as e:
            print(f"⚠️ Connexion perdue: {e}")
            print("🔄 Reconnexion dans 5 secondes...")
            time.sleep(5)
        except KeyboardInterrupt:
            print(f"\n🛑 Arrêt demandé. Total: {event_count} événements publiés.")
            break


def main():
    print("=" * 50)
    print("🚀 WikiScan Producer - Démarrage")
    print("=" * 50)
    
    # Créer le producer Kafka
    producer = create_kafka_producer()
    
    try:
        # Lancer le streaming
        stream_to_kafka(producer)
    finally:
        producer.flush()
        producer.close()
        print("👋 Producer arrêté proprement.")


if __name__ == "__main__":
    main()
