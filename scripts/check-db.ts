import "dotenv/config";
import pg from "pg";

const { Client } = pg;
const connectionString = process.env.DATABASE_URL;
if (!connectionString) throw new Error("DATABASE_URL is required");

const client = new Client({ connectionString });

async function main() {
  try {
    await client.connect();
    const db = await client.query<{ current_database: string; version: string }>(
      "SELECT current_database(), version()",
    );
    const extensions = await client.query<{ extname: string; extversion: string }>(
      "SELECT extname, extversion FROM pg_extension ORDER BY extname",
    );
    console.log(`Database: ${db.rows[0]?.current_database}`);
    console.log(`PostgreSQL: ${db.rows[0]?.version.split(" ").slice(0, 2).join(" ")}`);
    console.log("Extensions:");
    for (const extension of extensions.rows) {
      console.log(`- ${extension.extname} (${extension.extversion})`);
    }
  } finally {
    await client.end().catch(() => undefined);
  }
}

void main().catch((error: unknown) => {
  console.error(error instanceof Error ? error.message : error);
  process.exitCode = 1;
});
