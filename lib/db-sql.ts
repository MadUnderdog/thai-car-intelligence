import pg from "pg";

const pool = new pg.Pool({
  user: "hermes",
  password: "spidermax2026",
  host: "localhost",
  port: 5432,
  database: "thai_car_intelligence",
  max: 10,
});

export async function query(text: string, params: any[] = []) {
  const start = Date.now();
  const result = await pool.query(text, params);
  const duration = Date.now() - start;
  console.log("Query executed", { text: text.substring(0, 50), duration, rows: result.rowCount });
  return result.rows;
}

export default pool;
