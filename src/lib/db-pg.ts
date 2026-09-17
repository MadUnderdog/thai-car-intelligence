import pg from "pg";

const pool = new pg.Pool({
  user: process.env.DB_USER || "hermes",
  host: process.env.DB_HOST || "localhost",
  port: Number(process.env.DB_PORT) || 5432,
  database: process.env.DB_NAME || "thai_car_intelligence",
  max: 10,
});

export default pool;
