import express from "express";
import path from "path";
import { fileURLToPath } from "url";

const app = express();
const PORT = 3000;

const __filename = fileURLToPath(import.meta.url);
const __dirname = path.dirname(__filename);

app.use(express.static(path.join(__dirname, "public")));

app.use("/data", express.static(path.join(__dirname, "data")));

app.listen(PORT, () => {
  console.log(`OK, http://localhost:${PORT}`);
});
