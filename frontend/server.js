import express from "express";
import path from "path";
import {
  fileURLToPath
} from "url";
import {
  WebSocketServer
} from "ws";
import {
  createServer
} from "http";
import {
  Kafka
} from "kafkajs";
import fetch from "node-fetch";

const app = express();
const PORT = 3000;

const __filename = fileURLToPath(
  import.meta.url);
const __dirname = path.dirname(__filename);

// ======================
// CONFIGURATION KAFKA
// ======================
const KAFKA_BROKER = process.env.KAFKA_BROKER || "localhost:29092";
const KAFKA_TOPIC = "wiki-raw";

// ======================
// EXPRESS STATIC FILES
// ======================
app.use(express.static(path.join(__dirname, "public")));
app.use("/data", express.static(path.join(__dirname, "data")));
app.get("/api/offline/:eventType/by_country", async (req, res) => {
  const { eventType } = req.params;

  try {
    const listUrl =
      `http://localhost:9870/webhdfs/v1/wikiscan/offline_stats/${eventType}/by_country?op=LISTSTATUS`;

    const listRes = await fetch(listUrl);
    const listJson = await listRes.json();

    const files = listJson.FileStatuses.FileStatus
      .filter(f => f.pathSuffix.endsWith(".json"));

    let results = [];

    for (const file of files) {
      const openUrl =
        `http://localhost:9870/webhdfs/v1/wikiscan/offline_stats/${eventType}/by_country/${file.pathSuffix}?op=OPEN&noredirect=true`;

      const openRes = await fetch(openUrl);
      const openJson = await openRes.json();
      let dataUrl = openJson.Location;
      dataUrl = dataUrl.replace(
        /^http:\/\/[^:/]+/,
        "http://localhost"
      );
      const dataRes = await fetch(dataUrl);
      const text = await dataRes.text();

      const rows = text
        .trim()
        .split("\n")
        .map(line => JSON.parse(line));

      results.push(...rows);
    }

    res.json(results);

  } catch (err) {
    console.error("WebHDFS error:", err);
    res.status(500).json({ error: "Failed to read offline data" });
  }
});

// ======================
// HTTP SERVER + WEBSOCKET
// ======================
const server = createServer(app);
const wss = new WebSocketServer({
  server
});

// Clients WebSocket connectes
const clients = new Set();

wss.on("connection", (ws) => {
  console.log("[WS] Nouveau client connecte");
  clients.add(ws);

  ws.on("close", () => {
    console.log("[WS] Client deconnecte");
    clients.delete(ws);
  });

  ws.on("error", (err) => {
    console.error("[WS] Erreur:", err.message);
    clients.delete(ws);
  });
});

// Broadcast un evenement a tous les clients
function broadcast(event) {
  const message = JSON.stringify(event);
  clients.forEach((client) => {
    if (client.readyState === 1) { // OPEN
      client.send(message);
    }
  });
}

// ======================
// KAFKA CONSUMER
// ======================
const kafka = new Kafka({
  clientId: "wikiscan-frontend",
  brokers: [KAFKA_BROKER],
  retry: {
    initialRetryTime: 1000,
    retries: 10
  }
});

const consumer = kafka.consumer({
  groupId: "wikiscan-frontend-group"
});

async function startKafkaConsumer() {
  console.log(`[KAFKA] Connexion a ${KAFKA_BROKER}...`);

  try {
    await consumer.connect();
    console.log("[KAFKA] Connecte!");

    await consumer.subscribe({
      topic: KAFKA_TOPIC,
      fromBeginning: false
    });
    console.log(`[KAFKA] Abonne au topic: ${KAFKA_TOPIC}`);

    await consumer.run({
      eachMessage: async ({
        topic,
        partition,
        message
      }) => {
        try {
          const event = JSON.parse(message.value.toString());

          // Broadcast aux clients WebSocket
          broadcast(event);

        } catch (err) {
          // Ignorer les messages mal formes
        }
      }
    });

  } catch (err) {
    console.error("[KAFKA] Erreur connexion:", err.message);
    console.log("[KAFKA] Nouvelle tentative dans 5 secondes...");
    setTimeout(startKafkaConsumer, 5000);
  }
}

// ======================
// DEMARRAGE
// ======================
server.listen(PORT, () => {
  console.log("=".repeat(50));
  console.log(`[SERVER] WikiScan Live - http://localhost:${PORT}`);
  console.log("=".repeat(50));

  // Demarrer le consumer Kafka
  startKafkaConsumer();
});

// Gestion de l'arret propre
process.on("SIGINT", async () => {
  console.log("\n[STOP] Arret en cours...");
  await consumer.disconnect();
  server.close();
  process.exit(0);
});